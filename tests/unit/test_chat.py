from unittest.mock import patch, MagicMock
from sqlmodel import select
from main import Conversation, Message


# ── 1. Unitario: función auxiliar ────────────────────────────────
def test_format_role_user():
    from main import format_role
    assert format_role("user") == "Usted"

def test_format_role_model():
    from main import format_role
    assert format_role("model") == "Chatbot"


# ── 2. Integración: POST /conversations/ ─────────────────────────
def test_crear_conversacion(client):
    response = client.post("/conversations/")

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["title"] == "Nueva conversación"


# ── 3. Integración: GET /conversations/ vacía ─────────────────────
def test_lista_conversaciones_vacia(client):
    response = client.get("/conversations/")

    assert response.status_code == 200
    assert response.json() == []


# ── 4. Conversación que no existe → 404 ──────────────────────────
def test_mensajes_conv_inexistente(client):
    response = client.get("/conversations/999/messages")

    assert response.status_code == 404
    assert "Conversación no encontrada" in response.json()["detail"]


# ── 5. Insertar datos directamente y leer vía endpoint ───────────
def test_historial_mensajes(client, session):
    conv = Conversation()
    session.add(conv)
    session.commit()
    session.refresh(conv)

    msg = Message(conversation_id=conv.id, role="user", content="Hola test")
    session.add(msg)
    session.commit()

    response = client.get(f"/conversations/{conv.id}/messages")

    assert response.status_code == 200
    msgs = response.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Hola test"
    assert msgs[0]["role"] == "user"


# ── 6. Endpoint de chat con Gemini mockeado ───────────────────────
def test_chat_endpoint(client, session):
    conv = Conversation()
    session.add(conv)
    session.commit()
    session.refresh(conv)

    mock_response = MagicMock()
    mock_response.text = "Soy una respuesta falsa de Gemini"

    with patch("main.genai.Client") as mock_client:
        mock_client.return_value.models.generate_content.return_value = mock_response

        response = client.post(
            f"/conversations/{conv.id}/chat",
            json={"message": "¿Qué es Python?"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "model"
    assert data["content"] == "Soy una respuesta falsa de Gemini"

    mensajes = session.exec(
        select(Message).where(Message.conversation_id == conv.id)
    ).all()
    assert len(mensajes) == 2
    assert mensajes[0].role == "user"
    assert mensajes[1].role == "model"