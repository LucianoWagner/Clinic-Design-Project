import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


async def synthesize_speech(text: str) -> bytes:
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=503,
            detail="ElevenLabs API Key no configurada en el servidor.",
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": settings.elevenlabs_api_key,
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=_extract_elevenlabs_error(exc.response),
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Timeout al conectar con ElevenLabs.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="No se pudo conectar con ElevenLabs.",
        ) from exc

    return response.content


def _extract_elevenlabs_error(response: httpx.Response) -> str:
    fallback = f"Error de ElevenLabs ({response.status_code})."
    try:
        data = response.json()
    except ValueError:
        return fallback

    detail = data.get("detail")
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message:
            return message
    if isinstance(detail, str) and detail:
        return detail
    return fallback


# ── Extracción del texto de voz ───────────────────────────────────────────────
import re as _re  # noqa: E402

_LIST_START = _re.compile(
    r"\n\s*[-*•]\s"          # - item  /  * item  /  • item
    r"|\n\s*\d+[.)]\s"       # 1. item / 2) item
    r"|\n\s*\n"              # línea en blanco entre párrafos (precede a listas)
    r"|\n\s*\*\*[^*]+\*\*",  # **Encabezado** de sección Markdown
    _re.MULTILINE,
)

_MAX_VOICE_CHARS = 400  # ElevenLabs cobra por caracter; acotar respuestas largas


def extract_spoken_text(full_text: str) -> str:
    """
    Devuelve solo la parte conversacional del texto, apta para síntesis de voz.

    - Sin listas: devuelve el texto completo (truncado si supera el límite).
    - Con listas: devuelve solo el párrafo introductorio antes de la primera lista,
      que es el resumen que el agente formula antes de listar los datos.
    """
    if not full_text:
        return ""

    match = _LIST_START.search(full_text)
    spoken = full_text[: match.start()].strip() if match else full_text.strip()

    if len(spoken) > _MAX_VOICE_CHARS:
        truncated = spoken[:_MAX_VOICE_CHARS]
        last_end = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        spoken = truncated[: last_end + 1] if last_end > 0 else truncated

    return spoken
