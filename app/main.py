"""
Punto de entrada de la aplicación FastAPI.

Lifespan:
  - Inicializa el checkpointer de LangGraph según el tipo de DB configurada:
      * PostgreSQL (producción/Docker): PostgresSaver conectado a la DB existente.
      * SQLite u otro (tests): MemorySaver en RAM.
  - El checkpointer se expone en app.state.checkpointer para uso en las rutas.
  - PostgresSaver.setup() crea las tablas internas de LangGraph si no existen
    (no usa Alembic, son tablas internas del framework).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import appointments, conversations, health, speech, tts
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa y cierra el checkpointer de LangGraph."""
    if settings.database_url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # Convierte la URL de SQLAlchemy al formato nativo de psycopg
        conn_string = settings.database_url.replace("postgresql+psycopg", "postgresql")
        async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
            await checkpointer.setup()  # Crea tablas de checkpointing si no existen
            app.state.checkpointer = checkpointer
            yield
    else:
        # Fallback para entornos de test con SQLite
        from langgraph.checkpoint.memory import MemorySaver

        app.state.checkpointer = MemorySaver()
        yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(appointments.router, prefix="/api")
app.include_router(speech.router, prefix="/api")
app.include_router(tts.router, prefix="/api")

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
