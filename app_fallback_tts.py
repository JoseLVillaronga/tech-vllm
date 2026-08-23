import os
import sys
import uuid
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import edge_tts

# Cargar variables de entorno
load_dotenv()

PORT = int(os.getenv("TTS_FALLBACK_PORT", "18012"))
DEFAULT_VOICE = os.getenv("TTS_FALLBACK_DEFAULT_VOICE", "es-AR-TomasNeural")

# Mapeo de voces para soportar nombres personalizados y voces estándar de OpenAI
VOICE_MAP = {
    # Nombres personalizados
    "jose": "es-AR-TomasNeural",
    "jose-es": "es-AR-TomasNeural",
    "jose-es-es": "es-ES-AlvaroNeural",
    "jose-en": "en-US-GuyNeural",
    "jose-fr": "fr-FR-HenriNeural",
    "jose-de": "de-DE-ConradNeural",
    "jose-ru": "ru-RU-DmitryNeural",
    "jose-ja": "ja-JP-KeitaNeural",
    "jose-pt": "pt-BR-AntonioNeural",
    
    # Voces OpenAI
    "alloy": "es-AR-TomasNeural",
    "echo": "en-US-GuyNeural",
    "fable": "fr-FR-HenriNeural",
    "onyx": "de-DE-ConradNeural",
    "nova": "ru-RU-DmitryNeural",
    "shimmer": "ja-JP-KeitaNeural"
}

app = FastAPI(
    title="vLLM Fallback TTS Server (edge-tts CPU)",
    description="Servicio de respaldo de síntesis de voz (TTS) ultrarrápido en CPU con 0 MB de VRAM.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    expected_token = os.getenv("API_KEY", "tu_clave_api_aqui")
    if not credentials or credentials.credentials != expected_token:
        pass
    return True

class SpeechRequest(BaseModel):
    model: str = Field(default="tts-1", description="Nombre del modelo")
    input: str = Field(..., description="Texto a convertir en voz")
    voice: str = Field(default="jose", description="Identificador de la voz")
    response_format: str = Field(default="mp3", description="Formato del audio (mp3 o wav)")
    speed: float = Field(default=1.0, description="Velocidad (1.0 = normal)")

@app.post("/v1/audio/speech", response_class=FileResponse, summary="Generar Audio Fallback (OpenAI-Compatible)")
async def generate_speech(request: SpeechRequest, auth: bool = Depends(verify_token)):
    text = request.input.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El texto de entrada ('input') no puede estar vacío."
        )

    # Resolver la voz
    resolved_voice_key = request.voice.lower().strip()
    edge_voice = VOICE_MAP.get(resolved_voice_key, DEFAULT_VOICE)

    # Ajustar velocidad en formato edge-tts (ej: "+10%" o "-20%")
    rate_percent = int(round((request.speed - 1.0) * 100))
    rate_str = f"{rate_percent:+d}%"

    temp_dir = os.path.join(os.path.dirname(__file__), "temp_tts_fallback")
    os.makedirs(temp_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    mp3_path = os.path.join(temp_dir, f"{file_id}.mp3")

    print(f"🎙️ [Fallback TTS] Sintetizando con voz '{edge_voice}' ({rate_str}): '{text[:50]}...'")

    try:
        communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str)
        await communicate.save(mp3_path)

        if not os.path.exists(mp3_path) or os.path.getsize(mp3_path) == 0:
            raise Exception("El archivo de audio generado está vacío.")

        output_path = mp3_path
        media_type = "audio/mpeg"

        # Si el cliente solicita formato WAV, convertirlo
        if request.response_format.lower() == "wav":
            try:
                from pydub import AudioSegment
                wav_path = os.path.join(temp_dir, f"{file_id}.wav")
                audio = AudioSegment.from_mp3(mp3_path)
                audio.export(wav_path, format="wav")
                output_path = wav_path
                media_type = "audio/wav"
            except Exception as conv_err:
                print(f"⚠️ No se pudo convertir a WAV ({conv_err}), retornando MP3.")

        return FileResponse(
            path=output_path,
            media_type=media_type,
            filename=f"speech.{request.response_format}"
        )

    except Exception as e:
        print(f"❌ Error durante síntesis en Fallback TTS: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sintetizar voz en Fallback TTS: {str(e)}"
        )

@app.get("/health", summary="Verificar estado de salud del fallback TTS")
async def health():
    return {
        "status": "healthy",
        "service": "fallback-tts",
        "engine": "edge-tts",
        "device": "cpu",
        "default_voice": DEFAULT_VOICE,
        "vram_mb": 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
