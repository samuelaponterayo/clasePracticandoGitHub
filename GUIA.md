# Guía del Proyecto: Chat con LLM

Esta guía explica todo lo que construimos clase a clase — qué es cada tecnología, por qué la usamos y cómo encaja con el resto.

---

## ¿Qué construimos?

Una aplicación de chat con inteligencia artificial. El usuario puede crear múltiples conversaciones, escribir mensajes y recibir respuestas de un modelo de lenguaje (Gemini de Google). La app tiene backend, base de datos, frontend y autenticación de usuarios.

---

## Clase 1 y 2 — FastAPI como backend

### ¿Qué es FastAPI?

FastAPI es un framework de Python para construir APIs web. Una API es la capa que recibe pedidos (requests) y devuelve respuestas — es el intermediario entre el frontend y la base de datos.

### ¿Qué es un endpoint?

Un endpoint es una URL que el servidor "escucha". Por ejemplo:

```
POST /conversations/     → crear una conversación
GET  /conversations/     → listar todas las conversaciones
POST /conversations/1/chat → enviar un mensaje a la conversación 1
```

### SQLModel — el ORM

Un ORM (Object Relational Mapper) te permite trabajar con la base de datos usando clases Python en lugar de escribir SQL a mano.

```python
# Sin ORM (SQL crudo):
cursor.execute("INSERT INTO conversation (title) VALUES ('Nueva')")

# Con SQLModel (ORM):
conv = Conversation(title="Nueva")
session.add(conv)
session.commit()
```

Definís el modelo una sola vez y el ORM se encarga del resto:

```python
class Conversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(default="Nueva conversación")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Frontend vanilla

El frontend está hecho con HTML, CSS y JavaScript puro — sin frameworks. Usa `fetch()` para comunicarse con la API:

```javascript
const res = await fetch('/conversations/', { method: 'POST' });
const conv = await res.json();
```

---

## Clase 3 — Docker y PostgreSQL

### ¿Por qué Docker?

Sin Docker, cada persona del equipo instala PostgreSQL de manera diferente, con versiones diferentes, configuraciones diferentes. Con Docker, todos corren exactamente el mismo contenedor.

### Levantar la base de datos

```bash
docker run --name chat-db \
  -e POSTGRES_USER=chat_user \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=chatdb \
  -p 5432:5432 \
  -d postgres:16
```

Este comando crea un contenedor con PostgreSQL. Los parámetros:
- `-e` → variables de entorno (usuario, contraseña, nombre de la DB)
- `-p 5432:5432` → expone el puerto 5432 del contenedor al 5432 de tu máquina
- `-d` → corre en background (detached)

La aplicación se conecta usando la URL:
```
DATABASE_URL=postgresql://chat_user:secret@localhost:5432/chatdb
```

### PgAdmin

PgAdmin es una interfaz visual para explorar y administrar la base de datos. Desde ahí podés ver las tablas, los datos, correr SQL manualmente y entender cómo se guarda todo.

---

## Clase 4 — Testing

### ¿Por qué testear?

El código que no se testea se rompe en silencio. Los tests te avisan cuando algo dejó de funcionar — antes de que llegue a producción.

### Tests unitarios

Prueban una función aislada, sin base de datos ni servidor:

```python
def test_format_role_user():
    assert format_role("user") == "Tú"
```

### Tests de integración

Prueban que los endpoints funcionan correctamente, usando una base de datos en memoria (SQLite):

```python
def test_crear_conversacion(client):
    response = client.post("/conversations/")
    assert response.status_code == 200
    assert response.json()["title"] == "Nueva conversación"
```

El truco está en el `conftest.py` — reemplaza la base de datos real por una en memoria para que los tests sean rápidos y no dejen datos sucios:

```python
@pytest.fixture
def session_fixture():
    engine = create_engine("sqlite://", ...)  # DB en memoria
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
```

### Tests E2E (End-to-End) con Playwright

Los tests E2E controlan un navegador real y simulan lo que haría un usuario:

```python
def test_crear_conversacion(page: Page):
    page.goto("http://localhost:8000")
    page.click("#new-conv-btn")
    expect(page.locator(".conv-item")).to_be_visible()
```

Para correrlos con el navegador visible:
```bash
npx playwright test tests/e2e/ --headed
```

---

## Clase 5 — Migraciones con Alembic

### El problema

Cuando tu app ya tiene datos en producción y necesitás cambiar el esquema de la base de datos (agregar una columna, crear una tabla nueva), ¿qué hacés?

- Si usás `create_all` sin más → no toca tablas existentes, el schema queda desincronizado
- Si borrás y recreás la DB → perdés todos los datos

### ¿Qué es Alembic?

Alembic es la herramienta de migraciones de SQLAlchemy. Cada cambio de schema queda como un archivo versionado en el repositorio — como un "git" para tu base de datos.

### Configuración

1. Instalar:
```bash
pip install alembic
```

2. Inicializar:
```bash
alembic init migrations
```

3. En `alembic.ini`, configurar la URL de la DB:
```
sqlalchemy.url = postgresql://chat_user:secret@localhost:5432/chatdb
```

4. En `migrations/env.py`, apuntar a tus modelos:
```python
from main import SQLModel
target_metadata = SQLModel.metadata
```

### Flujo de trabajo

Cada vez que cambiás un modelo:

```bash
# 1. Alembic compara tu código con la DB y genera el archivo
alembic revision --autogenerate -m "descripcion del cambio"

# 2. Revisás el archivo generado en migrations/versions/
# 3. Aplicás la migración
alembic upgrade head
```

El archivo generado contiene dos funciones:

```python
def upgrade():
    # Lo que se hace para avanzar (ej: ADD COLUMN)
    op.add_column('conversation', sa.Column('user_id', sa.Integer(), nullable=True))

def downgrade():
    # Lo que se hace para deshacer
    op.drop_column('conversation', 'user_id')
```

Alembic guarda en la tabla `alembic_version` en qué versión está la DB en cada momento.

### Comandos útiles

```bash
alembic upgrade head          # aplicar todas las migraciones pendientes
alembic downgrade -1          # deshacer la última migración
alembic current               # ver en qué versión está la DB
alembic history               # ver el historial de migraciones
```

---

## Clase 6 — Autenticación (Login y Registro)

### El modelo User

Agregamos una tabla `user` para guardar los usuarios registrados:

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
```

La contraseña **nunca se guarda en texto plano**. Se guarda un hash — una transformación unidireccional:

```python
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
```

### Relacionar conversaciones con usuarios

Cada conversación pertenece a un usuario:

```python
class Conversation(SQLModel, table=True):
    ...
    user_id: int | None = Field(default=None, foreign_key="user.id")
```

Este campo es una **foreign key** — apunta al `id` de la tabla `user`.

### Endpoints de auth

```
POST /register  → crear cuenta nueva
POST /login     → verificar credenciales, devolver datos del usuario
```

### ¿Por qué no hay JWT todavía?

JWT (JSON Web Tokens) es el estándar para manejar sesiones en APIs REST. Por ahora guardamos el usuario en `localStorage` del navegador y pasamos el `user_id` como query parameter. Esto es suficiente para demostrar el concepto, pero **no es seguro para producción** — cualquiera podría falsificar un `user_id`. JWT lo resolvemos en la próxima etapa.

---

## Estructura del proyecto

```
claseLlm/
├── main.py              ← Backend: modelos, endpoints, lógica
├── static/
│   ├── index.html       ← Frontend: estructura y estilos
│   └── app.js           ← Frontend: lógica JavaScript
├── migrations/
│   ├── env.py           ← Configuración de Alembic
│   └── versions/        ← Archivos de migración versionados
├── tests/
│   ├── conftest.py      ← Fixtures compartidas (DB en memoria)
│   ├── unit/
│   │   └── test_chat.py ← Tests unitarios e integración
│   └── e2e/
│       ├── test_e2e.py  ← Tests E2E con Playwright (Python)
│       └── mi-test.spec.ts ← Tests E2E con Playwright (TypeScript)
├── alembic.ini          ← Configuración global de Alembic
├── requirements.txt     ← Dependencias de Python
└── .env                 ← Variables de entorno (NO subir a git)
```

---

## Cómo levantar el proyecto desde cero

### Requisitos previos
- Python 3.10+
- Docker Desktop instalado y corriendo
- Node.js (para los tests E2E con TypeScript)

### Pasos

```bash
# 1. Clonar el repo
git clone <url>
cd claseLlm

# 2. Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Crear el archivo .env
echo "GEMINI_API_KEY=tu_clave_aqui" > .env
echo "DATABASE_URL=postgresql://chat_user:secret@localhost:5432/chatdb" >> .env

# 4. Levantar la base de datos con Docker
docker run --name chat-db \
  -e POSTGRES_USER=chat_user \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=chatdb \
  -p 5432:5432 \
  -d postgres:16

# 5. Aplicar todas las migraciones
alembic upgrade head

# 6. Correr el servidor
uvicorn main:app --reload
```

La app queda disponible en `http://localhost:8000`.

### Correr los tests

```bash
# Tests unitarios e integración
pytest tests/unit/

# Tests E2E (necesita el servidor corriendo)
npx playwright test tests/e2e/ --headed
```
