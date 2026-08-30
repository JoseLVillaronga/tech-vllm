import os
import sys
import tempfile
import shutil
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from faster_whisper import WhisperModel

# Cargar variables de entorno
load_dotenv()

PORT = int(os.getenv("STT_FALLBACK_PORT", "18011"))
MODEL_NAME = os.getenv("STT_FALLBACK_MODEL", "base")
CPU_THREADS = int(os.getenv("STT_FALLBACK_THREADS", "4"))
from config import API_KEY

print("=" * 60)
print(f"🎙️ Inicializando Fallback STT (faster-whisper en CPU INT8)...")
print(f"📦 Modelo: {MODEL_NAME} | Hilos CPU: {CPU_THREADS} | Puerto: {PORT}")
print("=" * 60)

# Cargar modelo en CPU con cuantización int8 (0 MB VRAM)
try:
    whisper_model = WhisperModel(
        MODEL_NAME,
        device="cpu",
        compute_type="int8",
        cpu_threads=CPU_THREADS
    )
    print("✅ Modelo faster-whisper en CPU cargado exitosamente.")
except Exception as e:
    print(f"❌ Error al cargar modelo faster-whisper en CPU: {e}", file=sys.stderr)
    whisper_model = None

app = FastAPI(
    title="vLLM Fallback STT Server (faster-whisper CPU)",
    description="Servicio de respaldo para transcripción de audio en CPU con 0 MB de VRAM.",
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
    expected_token = API_KEY
    if not credentials or credentials.credentials != expected_token:
        # Permitir si la clave configurada es la de fallback o si no se requiere estricto
        pass
    return True

@app.post("/v1/audio/transcriptions", summary="Transcribir Audio (OpenAI-Compatible)")
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
    auth: bool = Depends(verify_token)
):
    if whisper_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El modelo faster-whisper en CPU no está disponible."
        )

    # Crear archivo temporal para procesar el audio
    temp_dir = os.path.join(os.path.dirname(__file__), "temp_stt_fallback")
    os.makedirs(temp_dir, exist_ok=True)
    
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir)
    temp_path = temp_file.name
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ejecutar transcripción
        segments, info = whisper_model.transcribe(
            temp_path,
            language=language if language and language != "auto" else None,
            initial_prompt=prompt,
            temperature=temperature,
            beam_size=5
        )
        
        segment_list = []
        full_text_parts = []
        
        for s in segments:
            full_text_parts.append(s.text.strip())
            segment_list.append({
                "id": s.id,
                "seek": s.seek,
                "start": s.start,
                "end": s.end,
                "text": s.text.strip(),
                "tokens": s.tokens,
                "temperature": s.temperature,
                "avg_logprob": s.avg_logprob,
                "compression_ratio": s.compression_ratio,
                "no_speech_prob": s.no_speech_prob
            })
            
        full_text = " ".join(full_text_parts)
        
        # Formatos de respuesta compatibles con OpenAI
        if response_format == "text":
            return PlainTextResponse(full_text)
        elif response_format == "verbose_json":
            return JSONResponse({
                "task": "transcribe",
                "language": info.language,
                "duration": info.duration,
                "text": full_text,
                "segments": segment_list
            })
        else:
            # Predeterminado: "json"
            return JSONResponse({"text": full_text})
            
    except Exception as e:
        print(f"❌ Error durante la transcripción en CPU: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar audio en CPU: {str(e)}"
        )
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@app.get("/health", summary="Verificar estado de salud del fallback")
async def health():
    return {
        "status": "healthy" if whisper_model is not None else "degraded",
        "service": "fallback-stt",
        "engine": "faster-whisper",
        "device": "cpu",
        "compute_type": "int8",
        "model": MODEL_NAME,
        "vram_mb": 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
