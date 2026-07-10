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
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

from app.api.routes import appointments, auth, conversations, doctor, health, speech, tts
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()


# --- Parche defensivo para fastapi-limiter ---
# Evita el error 'AttributeError: _IncludedRouter object has no attribute path'
# causado por la estructura interna en versiones modernas de FastAPI al agrupar rutas.
import fastapi_limiter.depends
from fastapi import Request, Response
original_limiter_call = fastapi_limiter.depends.RateLimiter.__call__

async def safe_rate_limiter_call(self, request: Request, response: Response):
    valid_routes = [r for r in request.app.routes if hasattr(r, "path") and hasattr(r, "methods")]
    original_routes = request.app.router.routes
    request.app.router.routes = valid_routes
    try:
        return await original_limiter_call(self, request, response)
    finally:
        request.app.router.routes = original_routes

fastapi_limiter.depends.RateLimiter.__call__ = safe_rate_limiter_call
# ---------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa y cierra el checkpointer de LangGraph."""
    redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(redis_client)

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
app.include_router(auth.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(appointments.router, prefix="/api")
app.include_router(doctor.router, prefix="/api")
app.include_router(speech.router, prefix="/api")
app.include_router(tts.router, prefix="/api")

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
