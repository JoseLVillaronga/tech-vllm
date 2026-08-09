import os
import uuid
import shutil
import torch
from fastapi import FastAPI, HTTPException, status, Depends, Security, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

PORT = int(os.getenv("DIARIZATION_PORT", "8003"))
HF_TOKEN = os.getenv("HF_TOKEN")

# Inicializar pipeline de PyAnnote (con soporte lazy-loading para manejar errores de tokens/TOS)
pipeline = None
init_error = None

def get_pipeline():
    global pipeline, init_error
    if pipeline is not None:
        return pipeline
        
    if not HF_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HF_TOKEN no configurado en el archivo .env. "
                "Para usar PyAnnote 3.1 necesitas una API key de Hugging Face."
            )
        )
        
    try:
        from pyannote.audio import Pipeline
        print("🧠 Cargando modelo de diarización PyAnnote 3.1 en GPU (CUDA)...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=HF_TOKEN
        )
        if pipeline is None:
            raise Exception("No se pudo instanciar el pipeline. Revisa que hayas aceptado los términos en Hugging Face.")
            
        # Forzar ejecución en GPU
        pipeline.to(torch.device("cuda"))
        print("✅ Pipeline de PyAnnote cargado correctamente en GPU (CUDA).")
        init_error = None
        return pipeline
    except Exception as e:
        init_error = str(e)
        print(f"⚠️ Error al inicializar PyAnnote: {e}")
        
        # Ofrecer instrucciones precisas en caso de que sea un repositorio protegido (Gated Repo)
        if "gated" in init_error.lower() or "401" in init_error or "403" in init_error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acceso Denegado a PyAnnote. Asegúrate de haber iniciado sesión y aceptado "
                    "los términos de uso en las siguientes URLs de Hugging Face:\n"
                    "1. https://huggingface.co/pyannote/speaker-diarization-3.1\n"
                    "2. https://huggingface.co/pyannote/segmentation-3.0\n"
                    "3. https://huggingface.co/pyannote/speaker-diarization-community-1"
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al inicializar PyAnnote: {init_error}"
            )

# Inicializar FastAPI
app = FastAPI(
    title="vLLM OpenAI-Compatible Speaker Diarization Server",
    description=(
        "Servicio local persistente de Diarización de Voz (Identificación de Hablantes).\n\n"
        "Carga los modelos en CPU para consumir 0 VRAM y expone una API REST para procesar audios en milisegundos."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar esquema de seguridad HTTP Bearer para Swagger UI
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    expected_token = os.getenv("API_KEY", "tu_clave_api_aqui")
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o no proporcionada en la cabecera Authorization."
        )
    return token

@app.post("/v1/audio/diarize", summary="Identificar Hablantes (Speaker Diarization)")
async def diarize_audio(
    file: UploadFile = File(..., description="Archivo de audio local (.wav, .mp3, .flac)"),
    token: str = Depends(verify_token)
):
    """
    Sube un archivo de audio, ejecuta la diarización de PyAnnote en la CPU y devuelve una línea de tiempo estructurada por hablante.
    """
    # Cargar / Verificar el pipeline
    pyannote_pipeline = get_pipeline()

    # Directorio temporal para guardar el audio recibido
    temp_dir = os.path.join(os.path.dirname(__file__), "temp_diarization")
    os.makedirs(temp_dir, exist_ok=True)

    # Generar un nombre único para el archivo de entrada temporal
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".wav"
    temp_filepath = os.path.join(temp_dir, f"{file_id}{ext}")

    try:
        # Guardar archivo de audio temporalmente en disco
        with open(temp_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"🎙️ Ejecutando diarización en '{file.filename}' usando GPU (CUDA)...")
        
        # Ejecutar inferencia
        diarization_result = pyannote_pipeline(temp_filepath)
        
        # Compatibilidad con PyAnnote v3 (Annotation) y v4 (DiarizeOutput)
        if hasattr(diarization_result, "speaker_diarization"):
            annotation = diarization_result.speaker_diarization
        else:
            annotation = diarization_result
            
        # Parsear marcas de tiempo
        segments = []
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            segments.append({
                "start": round(turn.start, 2),
                "end": round(turn.end, 2),
                "speaker": speaker
            })
            
        print(f"✅ Diarización completada. Encontrados {len(segments)} segmentos de voz.")
        return JSONResponse(content={"segments": segments})

    except Exception as e:
        print(f"❌ Error durante la diarización: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante el procesamiento del audio: {str(e)}"
        )
    finally:
        # Eliminar archivo temporal
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

@app.get("/health", summary="Verificar estado del servicio")
async def health_check():
    return {
        "status": "healthy" if init_error is None else "degraded",
        "detail": "PyAnnote cargado correctamente en CPU" if init_error is None else f"Error: {init_error}",
        "device": "cpu"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
