# main.py — versión nueva
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from typing import Annotated
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import hashlib
import os

load_dotenv()

from google import genai


def format_role(role: str) -> str:
    return "Tú" if role == "user" else "Chatbot"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ── Modelos ──────────────────────────────────────────────
class User(SQLModel, table=True):
      id: int | None = Field(default=None, primary_key=True)
      username: str = Field(unique=True, index=True)
      password_hash: str
      conversations: list["Conversation"] = Relationship(back_populates="user")

class Conversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(default="Nueva conversación")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list["Message"] = Relationship(back_populates="conversation")
    user_id: int | None = Field(default=None, foreign_key="user.id")
    user: User | None = Relationship(back_populates="conversations")

class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id")
    role: str  # "user" o "model"
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    conversation: Conversation | None = Relationship(back_populates="messages")


# ── Schemas de respuesta (separar tabla de lo que devolvemos) ──
class MessageOut(SQLModel):
    id: int
    role: str
    content: str
    created_at: datetime


class ConversationOut(SQLModel):
    id: int
    title: str
    created_at: datetime


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str


class ConversationUpdate(BaseModel):
    title: str


class ChatRequest(BaseModel):
    message: str


# ── Base de datos ─────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# ── App ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


# ── Auth ──────────────────────────────────────────────────────
@app.post("/register", response_model=UserOut)
def register(body: RegisterRequest, session: SessionDep):
    existing = session.exec(select(User).where(User.username == body.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    user = User(username=body.username, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.post("/login", response_model=UserOut)
def login(body: LoginRequest, session: SessionDep):
    user = session.exec(select(User).where(User.username == body.username)).first()
    if not user or user.password_hash != hash_password(body.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return user


# ── Endpoints de Conversaciones ───────────────────────────────
@app.post("/conversations/", response_model=ConversationOut)
def create_conversation(session: SessionDep, user_id: int | None = Query(default=None)):
    conv = Conversation(user_id=user_id)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


@app.get("/conversations/", response_model=list[ConversationOut])
def list_conversations(session: SessionDep, user_id: int | None = Query(default=None)):
    query = select(Conversation)
    if user_id:
        query = query.where(Conversation.user_id == user_id)
    return session.exec(query).all()


@app.patch("/conversations/{conv_id}", response_model=ConversationOut)
def rename_conversation(conv_id: int, body: ConversationUpdate, session: SessionDep):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    conv.title = body.title
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


@app.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def get_messages(conv_id: int, session: SessionDep):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return session.exec(select(Message).where(Message.conversation_id == conv_id)).all()


@app.post("/conversations/{conv_id}/chat", response_model=MessageOut)
def chat(conv_id: int, body: ChatRequest, session: SessionDep):
    # 1. Verificar que existe la conversación
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    # 2. Guardar mensaje del usuario
    user_msg = Message(conversation_id=conv_id, role="user", content=body.message)
    session.add(user_msg)
    session.commit()

    # 3. Cargar historial para enviar contexto a Gemini
    history = session.exec(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    ).all()

    # 4. Llamar a Gemini con todo el historial
    client = genai.Client()
    gemini_history = [
        {"role": msg.role, "parts": [{"text": msg.content}]}
        for msg in history[:-1]  # todo excepto el último (recién guardado)
    ]

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=gemini_history + [{"role": "user", "parts": [{"text": body.message}]}],
    )

    # 5. Guardar respuesta del modelo
    bot_msg = Message(conversation_id=conv_id, role="model", content=response.text)
    session.add(bot_msg)
    session.commit()
    session.refresh(bot_msg)

    return bot_msg
