from fastapi import APIRouter, Response, Depends
from fastapi_limiter.depends import RateLimiter

from app.services.tts_service import SynthesisRequest, synthesize_speech

router = APIRouter(tags=["tts"])


@router.post("/tts", dependencies=[Depends(RateLimiter(times=20, seconds=60))])
async def synthesize(payload: SynthesisRequest) -> Response:
    audio = await synthesize_speech(payload.text)
    return Response(content=audio, media_type="audio/mpeg")
