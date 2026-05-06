from fastapi import APIRouter, Response

from app.services.tts_service import SynthesisRequest, synthesize_speech

router = APIRouter(tags=["tts"])


@router.post("/tts")
async def synthesize(payload: SynthesisRequest) -> Response:
    audio = await synthesize_speech(payload.text)
    return Response(content=audio, media_type="audio/mpeg")
