import os
import uuid
import shutil
import base64
from fastapi import FastAPI, HTTPException, status, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from huggingface_hub import hf_hub_download
from dotenv import load_dotenv
from f5_tts.api import F5TTS

# Cargar variables de entorno
load_dotenv()

# Puerto predeterminado: 8002
PORT = int(os.getenv("TTS_PORT", "8002"))

# Configuración del modelo F5-TTS para el servidor
# Por defecto cargamos el modelo en Español, pero es 100% configurable
MODEL_REPO = os.getenv("TTS_MODEL_REPO_ID", "jpgallegoar/F5-Spanish")
MODEL_FILE = os.getenv("TTS_MODEL_FILE", "model_1200000.safetensors")
MODEL_TYPE = os.getenv("TTS_MODEL_TYPE", "F5TTS_Base")  # F5TTS_Base para comunitarios, F5TTS_v1_Base para oficial
VOCAB_FILE = os.getenv("TTS_VOCAB_FILE", "vocab.txt")

# Ruta de audios de referencia predeterminados
REF_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "mi_voz_24k_mono.wav")
REF_TEXT_DEFAULT = os.getenv("TTS_REF_TEXT_DEFAULT", "Hola, este es un ejemplo de mi voz grabado para entrenar el modelo de síntesis de voz F5-TTS en mi computadora.")

print("=" * 60)
print("📥 Descargando/Verificando checkpoint de F5-TTS...")
ckpt_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
vocab_path = hf_hub_download(repo_id=MODEL_REPO, filename=VOCAB_FILE)

print("🧠 Cargando modelo F5-TTS en GPU (VRAM)...")
f5tts = F5TTS(model=MODEL_TYPE, ckpt_file=ckpt_path, vocab_file=vocab_path, device="cuda")
print("✅ Modelo cargado con éxito en GPU!")
print("=" * 60)

# Inicializar FastAPI
app = FastAPI(
    title="vLLM OpenAI-Compatible F5-TTS Server",
    description="Servicio local persistente de Texto a Voz (TTS) con Clonación de Voz al vuelo.",
    version="1.0.0",
    docs_url="/docs",  # Exponer Swagger UI en la ruta /docs
    redoc_url="/redoc"
)

# Configurar CORS para permitir conexiones externas (como Open-WebUI)
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
    """
    Verifica que el token enviado en la cabecera 'Authorization' coincida con la clave API del proyecto.
    """
    token = credentials.credentials
    expected_token = os.getenv("API_KEY", "token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939")
    if token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o no proporcionada en la cabecera Authorization."
        )
    return token

# Definir la estructura del payload compatible con OpenAI
class SpeechRequest(BaseModel):
    model: str = Field(default="tts-1", description="Nombre del modelo (por ejemplo, tts-1)")
    input: str = Field(..., description="El texto que quieres convertir a voz.")
    voice: str = Field(
        default="jose", 
        description=(
            "Identificador de la voz de referencia a clonar. Opciones:\n"
            "- **'jose'** o **'jose-es'**: Clona tu voz en español usando 'mi_voz_24k_mono.wav' "
            "y su correspondiente transcripción en español. Nota: F5-TTS soporta clonación cruzada de "
            "idiomas, lo que significa que puedes enviarle textos en inglés, francés, alemán, etc., "
            "y tu clon hablará en esos idiomas usando tu timbre de voz nativo.\n"
            "- **'default'**: Voz predeterminada en base al modelo configurado."
        )
    )
    response_format: str = Field(default="mp3", description="Formato del audio de salida (mp3 o wav)")
    speed: float = Field(default=1.0, description="Velocidad del audio generado (por defecto 1.0)")

@app.post("/v1/audio/speech", response_class=FileResponse, summary="Generar Audio desde Texto (OpenAI-compatible)")
async def text_to_speech(request: SpeechRequest, token: str = Depends(verify_token)):
    """
    Toma un texto de entrada, clona la voz de referencia configurada y genera el archivo de audio.
    """
    if not request.input.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El texto de entrada ('input') no puede estar vacío."
        )

    # Definir archivo de referencia en base a la voz seleccionada
    # Por defecto usamos el audio local 'mi_voz_24k_mono.wav'
    ref_file = REF_AUDIO_PATH
    ref_text = REF_TEXT_DEFAULT

    if not os.path.exists(ref_file):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se encontró el audio de referencia en {ref_file}. Asegúrate de que el archivo exista."
        )

    # Crear directorio temporal para guardar el audio de salida si no existe
    temp_dir = os.path.join(os.path.dirname(__file__), "temp_tts")
    os.makedirs(temp_dir, exist_ok=True)

    # Generar un nombre único para el archivo de salida
    file_id = str(uuid.uuid4())
    output_filename = f"{file_id}.{request.response_format}"
    output_path = os.path.join(temp_dir, output_filename)

    print(f"🎙️ Generando TTS para la voz '{request.voice}': '{request.input[:50]}...'")
    
    try:
        # Ejecutar inferencia de F5-TTS
        f5tts.infer(
            ref_file=ref_file,
            ref_text=ref_text,
            gen_text=request.input,
            speed=request.speed,
            file_wave=output_path
        )
        
        if not os.path.exists(output_path):
            raise Exception("El archivo de audio de salida no fue creado por el generador.")

        # Determinar el tipo de contenido (MIME)
        media_type = "audio/mpeg" if request.response_format.lower() == "mp3" else "audio/wav"
        
        return FileResponse(
            path=output_path,
            media_type=media_type,
            filename=f"speech.{request.response_format}"
        )

    except Exception as e:
        print(f"❌ Error durante la generación de audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del generador TTS: {str(e)}"
        )

@app.get("/health", summary="Verificar estado del servicio")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": MODEL_REPO,
        "device": "cuda"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
