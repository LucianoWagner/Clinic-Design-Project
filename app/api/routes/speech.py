from fastapi import APIRouter, HTTPException, Response, File, UploadFile
from pydantic import BaseModel

from app.services.tts_service import SynthesisRequest, synthesize_speech

router = APIRouter(tags=["speech"])


class TranscriptionRead(BaseModel):
    text: str


@router.post("/speech/transcribe", response_model=TranscriptionRead)
async def transcribe(audio_file: UploadFile = File(...)) -> TranscriptionRead:
    _ = audio_file
    raise HTTPException(
        status_code=501,
        detail="Fallback STT backend no configurado. Usá STT del navegador o agregá proveedor STT.",
    )


@router.post("/speech/synthesize")
async def synthesize(payload: SynthesisRequest) -> Response:
    audio = await synthesize_speech(payload.text)
    return Response(content=audio, media_type="audio/mpeg")
