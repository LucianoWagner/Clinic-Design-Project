from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

router = APIRouter(tags=["speech"])


class TranscriptionRead(BaseModel):
    text: str


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/speech/transcribe", response_model=TranscriptionRead)
async def transcribe(audio_file: UploadFile = File(...)) -> TranscriptionRead:
    _ = audio_file
    raise HTTPException(
        status_code=501,
        detail="Fallback STT backend no configurado. Usá STT del navegador o agregá proveedor STT.",
    )


@router.post("/speech/synthesize")
def synthesize(payload: SynthesisRequest) -> None:
    _ = payload
    raise HTTPException(
        status_code=501,
        detail="Fallback TTS backend no configurado. Usá SpeechSynthesis del navegador.",
    )
