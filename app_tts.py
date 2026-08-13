import os
import uuid
import shutil
import base64
import torch
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

# Puerto predeterminado: 18002 (interno detrás de gateway)
PORT = int(os.getenv("TTS_BACKEND_PORT", "18002"))

# Rutas de audios de referencia predeterminados
REF_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "mi_voz_24k_mono.wav")
REF_TEXT_DEFAULT = os.getenv("TTS_REF_TEXT_DEFAULT", "Hola, este es un ejemplo de mi voz grabado para entrenar el modelo de síntesis de voz F5-TTS en mi computadora.")

# Configuración de los checkpoints de F5-TTS por idioma
MODELS_CONFIG = {
    "es": {
        "repo_id": "jpgallegoar/F5-Spanish",
        "model_type": "F5TTS_Base",
        "ckpt_file": "model_1200000.safetensors",
        "vocab_file": "vocab.txt"
    },
    "en": {
        "repo_id": "SWivid/F5-TTS",
        "model_type": "F5TTS_v1_Base",
        "ckpt_file": "",  # Descarga automática interna por F5TTS
        "vocab_file": ""  # Descarga automática interna por F5TTS
    },
    "fr": {
        "repo_id": "RASPIAUDIO/F5-French-MixedSpeakers-reduced",
        "model_type": "F5TTS_Base",
        "ckpt_file": "model_last_reduced.pt",
        "vocab_file": "vocab.txt"
    },
    "de": {
        "repo_id": "aihpi/F5-TTS-German",
        "model_type": "F5TTS_Base",
        "ckpt_file": "F5TTS_Base/model_420000.safetensors",
        "vocab_file": "vocab.txt"
    },
    "ru": {
        "repo_id": "hotstone228/F5-TTS-Russian",
        "model_type": "F5TTS_Base",
        "ckpt_file": "model_last.safetensors",
        "vocab_file": "vocab.txt"
    },
    "ja": {
        "repo_id": "Jmica/F5TTS",
        "model_type": "F5TTS_Base",
        "ckpt_file": "JA_21999120/model_21999120.pt",
        "vocab_file": "JA_21999120/vocab_japanese.txt"
    },
    "pt": {
        "repo_id": "firstpixel/F5-TTS-pt-br",
        "model_type": "F5TTS_Base",
        "ckpt_file": "pt-br/model_last.safetensors",
        "vocab_file": ""
    }
}

# Mapeo de voces para soportar nombres explícitos y las voces hardcodeadas de Open-WebUI
VOICE_MAP = {
    # Voces explícitas de idioma
    "jose": "es",
    "jose-es": "es",
    "jose-en": "en",
    "jose-fr": "fr",
    "jose-de": "de",
    "jose-ru": "ru",
    "jose-ja": "ja",
    "jose-pt": "pt",
    
    # Voces OpenAI (Mapeadas a los modelos correspondientes)
    "alloy": "es",    # Mapea a Español
    "echo": "en",     # Mapea a Inglés
    "fable": "fr",    # Mapea a Francés
    "onyx": "de",     # Mapea a Alemán
    "nova": "ru",     # Mapea a Ruso
    "shimmer": "ja",  # Mapea a Japonés
}

class MultilingualTTSManager:
    def __init__(self):
        self.instances = {}
        self.active_lang = None

    def get_model(self, lang: str):
        if lang not in MODELS_CONFIG:
            lang = "es"
            
        if lang not in self.instances:
            cfg = MODELS_CONFIG[lang]
            print(f"📥 Descargando/Cargando checkpoint F5-TTS para el idioma '{lang}'...")
            
            try:
                if cfg["ckpt_file"]:
                    ckpt_path = hf_hub_download(repo_id=cfg["repo_id"], filename=cfg["ckpt_file"])
                    if cfg["vocab_file"]:
                        vocab_path = hf_hub_download(repo_id=cfg["repo_id"], filename=cfg["vocab_file"])
                        instance = F5TTS(model=cfg["model_type"], ckpt_file=ckpt_path, vocab_file=vocab_path, device="cpu")
                    else:
                        instance = F5TTS(model=cfg["model_type"], ckpt_file=ckpt_path, device="cpu")
                else:
                    # El modelo oficial de Inglés no necesita ckpt_file específico
                    instance = F5TTS(model=cfg["model_type"], device="cpu")
                    
                self.instances[lang] = instance
                print(f"✅ Modelo '{lang}' instanciado en CPU exitosamente.")
            except Exception as e:
                print(f"❌ Error al instanciar el modelo para '{lang}': {e}")
                raise e
                
        return self.instances[lang]

    def activate_model(self, lang: str):
        if lang not in MODELS_CONFIG:
            lang = "es"
            
        # Si ya está activo en la GPU, lo retornamos inmediatamente
        if self.active_lang == lang:
            return self.instances[lang]

        # 1. Si hay otro modelo activo en GPU, lo movemos a CPU
        if self.active_lang is not None:
            old_lang = self.active_lang
            print(f"💾 Moviendo modelo F5-TTS '{old_lang}' a CPU (liberando VRAM)...")
            old_instance = self.instances[old_lang]
            old_instance.ema_model.to("cpu")
            if hasattr(old_instance.vocoder, "to"):
                old_instance.vocoder.to("cpu")
            old_instance.device = "cpu"
            
        # 2. Traemos el nuevo modelo a GPU
        instance = self.get_model(lang)
        print(f"⚡ Cargando modelo F5-TTS '{lang}' en GPU (CUDA)...")
        instance.ema_model.to("cuda")
        if hasattr(instance.vocoder, "to"):
            instance.vocoder.to("cuda")
        instance.device = "cuda"
        
        self.active_lang = lang
        print(f"🚀 Modelo '{lang}' activo en la GPU para inferencia.")
        
        # Limpiar caché de CUDA
        torch.cuda.empty_cache()
        
        return instance

# Inicializar el administrador de modelos
manager = MultilingualTTSManager()

# Pre-cargar el modelo en Español en GPU durante el inicio para que responda rápido
print("=" * 60)
print("🧠 Inicializando modelo en Español (predeterminado) en GPU...")
manager.activate_model("es")
print("=" * 60)

# Inicializar FastAPI
app = FastAPI(
    title="vLLM OpenAI-Compatible Multilingual F5-TTS Server",
    description=(
        "Servicio local persistente de Texto a Voz (TTS) con Clonación de Voz al vuelo.\n\n"
        "Administra dinámicamente múltiples checkpoints (ES, EN, FR, DE, RU, JA) "
        "intercambiándolos en la GPU para una pronunciación nativa perfecta sin gastar VRAM de más."
    ),
    version="2.0.0",
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

class SpeechRequest(BaseModel):
    model: str = Field(default="tts-1", description="Nombre del modelo (por ejemplo, tts-1)")
    input: str = Field(..., description="El texto que quieres convertir a voz.")
    voice: str = Field(
        default="jose", 
        description=(
            "Identificador de la voz/idioma a clonar. El servidor cargará automáticamente el acento correspondiente:\n"
            "- **'jose'** o **'jose-es'** (o voz OpenAI **'alloy'**): Pronunciación nativa en Español.\n"
            "- **'jose-en'** (o voz OpenAI **'echo'**): Pronunciación nativa en Inglés.\n"
            "- **'jose-fr'** (o voz OpenAI **'fable'**): Pronunciación nativa en Francés.\n"
            "- **'jose-de'** (o voz OpenAI **'onyx'**): Pronunciación nativa en Alemán.\n"
            "- **'jose-ru'** (o voz OpenAI **'nova'**): Pronunciación nativa en Ruso.\n"
            "- **'jose-ja'** (o voz OpenAI **'shimmer'**): Pronunciación nativa en Japonés.\n\n"
            "*Nota: Todas las opciones clonan tu timbre de voz a partir de tu archivo 'mi_voz_24k_mono.wav'.*"
        )
    )
    response_format: str = Field(default="mp3", description="Formato del audio de salida (mp3 o wav)")
    speed: float = Field(default=1.0, description="Velocidad del audio generado (por defecto 1.0)")

@app.post("/v1/audio/speech", response_class=FileResponse, summary="Generar Audio desde Texto (OpenAI-compatible)")
async def text_to_speech(request: SpeechRequest, token: str = Depends(verify_token)):
    """
    Toma un texto de entrada, carga dinámicamente el modelo del idioma resuelto por la voz y genera el archivo clonando tu voz.
    """
    if not request.input.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El texto de entrada ('input') no puede estar vacío."
        )

    # Resolver el idioma correspondiente a la voz solicitada
    resolved_voice = request.voice.lower().strip()
    lang = VOICE_MAP.get(resolved_voice, "es")

    # Mover el modelo de este idioma a la GPU (liberando el anterior si correspondiese)
    try:
        active_f5 = manager.activate_model(lang)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo cargar el modelo para el idioma '{lang}': {str(e)}"
        )

    # Determinar el audio y texto de referencia a usar (MongoDB con fallback)
    ref_file = REF_AUDIO_PATH
    ref_text = REF_TEXT_DEFAULT
    
    try:
        from pymongo import MongoClient
        mongo_user = os.getenv("MONGO_USER", "admin")
        mongo_pass = os.getenv("MONGO_PASS", "joseMDB365$")
        mongo_host = os.getenv("MONGO_HOST", "127.0.0.1")
        mongo_db = os.getenv("MONGO_DB", "vllm")
        mongo_uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:27017/{mongo_db}?authSource=admin"
        
        # Conexión rápida con timeout de 1.5s
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
        db = client[mongo_db]
        active_voice = db.reference_voices.find_one({"is_active": True})
        if active_voice and active_voice.get("audio_path") and os.path.exists(active_voice["audio_path"]):
            ref_file = active_voice["audio_path"]
            ref_text = active_voice.get("text", "")
            print(f"🗣️ Utilizando voz de referencia personalizada: '{active_voice['name']}'")
    except Exception as e:
        print(f"⚠️ Advertencia: No se pudo consultar MongoDB ({e}). Usando fallback local predeterminado.")

    if not os.path.exists(ref_file):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se encontró el audio de referencia en {ref_file}."
        )

    # Crear directorio temporal si no existe
    temp_dir = os.path.join(os.path.dirname(__file__), "temp_tts")
    os.makedirs(temp_dir, exist_ok=True)

    # Nombre único para el audio generado
    file_id = str(uuid.uuid4())
    output_filename = f"{file_id}.{request.response_format}"
    output_path = os.path.join(temp_dir, output_filename)

    print(f"🎙️ Generando TTS con acento '{lang}' (voz '{request.voice}'): '{request.input[:50]}...'")
    
    try:
        # Generar inferencia con el F5TTS seleccionado
        active_f5.infer(
            ref_file=ref_file,
            ref_text=ref_text,
            gen_text=request.input,
            speed=request.speed,
            file_wave=output_path
        )
        
        if not os.path.exists(output_path):
            raise Exception("El archivo de audio de salida no fue creado.")

        media_type = "audio/mpeg" if request.response_format.lower() == "mp3" else "audio/wav"
        
        return FileResponse(
            path=output_path,
            media_type=media_type,
            filename=f"speech.{request.response_format}"
        )

    except Exception as e:
        print(f"❌ Error durante la generación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del generador TTS: {str(e)}"
        )

@app.get("/health", summary="Verificar estado del servicio")
async def health_check():
    return {
        "status": "healthy",
        "active_language": manager.active_lang,
        "instantiated_languages": list(manager.instances.keys()),
        "device": "cuda"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
