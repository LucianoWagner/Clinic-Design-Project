from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Consultorio Agent"
    environment: str = "development"
    database_url: str = "sqlite:///./consultorio.db"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    hold_ttl_seconds: int = 300
    # Límite de iteraciones del loop ReAct (cada iteración = LLM call + tool calls)
    max_agent_iterations: int = 6
    # Ventana de mensajes de historial para reconstruir contexto (fallback sin checkpointer)
    max_context_messages: int = 12
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    jwt_secret_key: str = "dev-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    
    # Configuración TTS (ElevenLabs)
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJcg"  # Voice 'Fin' por defecto

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
