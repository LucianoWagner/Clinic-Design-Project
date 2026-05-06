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
