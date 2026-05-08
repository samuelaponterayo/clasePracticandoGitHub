# claseLlm

Repositorio de clases prácticas sobre el desarrollo de software con LLMs.

## Clases

1. **FastAPI como backend** — endpoints REST, integración con LLM, frontend con HTML, CSS y JavaScript
2. **Docker para Postgres y PgAdmin** — contenerización de la base de datos, configuración de PgAdmin
3. **Intro a Testing** — primeros pasos con testing en Python, pytest, estructura de tests
4. **E2E Testing** — pruebas end-to-end con Playwright, automatización del navegador

---

## Requisitos para correr el proyecto

### 1. API Key de Gemini

Creá un archivo `.env` en la raíz del proyecto con tu clave:

```
GEMINI_API_KEY=tu_api_key_aqui
```

### 2. Base de datos (Docker)

Necesitás tener **Docker Desktop abierto** antes de correr el siguiente comando:

```bash
docker run --name chat-db \
  -e POSTGRES_USER=chat_user \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=chatdb \
  -p 5432:5432 \
  -d postgres:16
```

Luego agregá también en tu `.env`:

```
DATABASE_URL=postgresql://chat_user:secret@localhost:5432/chatdb
```

> Si ya corriste el contenedor antes, usá `docker start chat-db` en lugar del comando de arriba.
