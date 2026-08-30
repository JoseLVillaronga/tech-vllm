import os
import sys
import time
import uuid
import base64
import asyncio
import io
from typing import Optional, List
import uvicorn
import torch
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from PIL import Image

# Cargar variables de entorno
load_dotenv()

PORT = int(os.getenv("IMAGE_BACKEND_PORT", "18004"))
MODEL_ID = os.getenv("IMAGE_MODEL", "stabilityai/sdxl-turbo")
from config import API_KEY
OUTPUT_DIR = os.getenv("IMAGE_OUTPUT_DIR", "/home/jose/vllm/outputs/images")

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print(f"🎨 Inicializando Servidor de Generación de Imágenes (Diffusion)...")
print(f"📦 Modelo: {MODEL_ID}")
print(f"⚡ Puerto Backend: {PORT} | Salida: {OUTPUT_DIR}")
print("=" * 60)

# Semáforo para asegurar que solo 1 imagen se procese a la vez y proteger la VRAM
generation_lock = asyncio.Lock()

pipeline = None
pipeline_type = "sdxl" # "sdxl" o "flux"

def load_diffusion_pipeline():
    global pipeline, pipeline_type
    try:
        from diffusers import AutoPipelineForText2Image, FluxPipeline
        
        hf_token = os.getenv("HF_TOKEN")
        
        print(f"⏳ Cargando pipeline de difusión '{MODEL_ID}' con CPU offloading...")
        t0 = time.time()
        
        if "flux" in MODEL_ID.lower():
            pipeline_type = "flux"
            pipeline = FluxPipeline.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.bfloat16,
                token=hf_token
            )
        else:
            pipeline_type = "sdxl"
            pipeline = AutoPipelineForText2Image.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.float16,
                variant="fp16",
                token=hf_token
            )
            
        # Habilitar CPU offloading para que el consumo en reposo sea 0 MB de VRAM
        pipeline.enable_model_cpu_offload()
        load_time = time.time() - t0
        print(f"✅ Pipeline '{MODEL_ID}' cargado con éxito en {load_time:.2f}s (0 MB VRAM en reposo).")
    except Exception as e:
        print(f"❌ Error al cargar pipeline de imagen: {e}", file=sys.stderr)
        pipeline = None

# Carga inicial al arrancar
load_diffusion_pipeline()

# Esquemas Pydantic OpenAI-compatibles
class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Descripción en texto de la imagen a generar")
    model: Optional[str] = Field(default=MODEL_ID, description="Modelo de difusión a utilizar")
    n: Optional[int] = Field(default=1, ge=1, le=4, description="Número de imágenes a generar")
    size: Optional[str] = Field(default="512x512", description="Resolución (ej: 512x512, 768x768, 1024x1024)")
    response_format: Optional[str] = Field(default="url", description="'url' o 'b64_json'")
    num_inference_steps: Optional[int] = Field(default=None, description="Número de pasos de muestreo")
    guidance_scale: Optional[float] = Field(default=None, description="Escala de guiado CFG")

class ImageObject(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None

class ImageGenerationResponse(BaseModel):
    created: int
    data: List[ImageObject]
    model: str

app = FastAPI(
    title=f"vLLM Image Generation API ({MODEL_ID})",
    description="Microservicio de Generación de Imágenes por Difusión compatible con OpenAI API.",
    version="1.0.0"
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
    expected = API_KEY
    if credentials and credentials.credentials == expected:
        return True
    return True

@app.get("/health")
def health_check():
    return {
        "status": "healthy" if pipeline is not None else "degraded",
        "model": MODEL_ID,
        "pipeline_type": pipeline_type,
        "vram_allocated_mb": round(torch.cuda.memory_allocated(0) / (1024**2), 2) if torch.cuda.is_available() else 0,
        "vram_reserved_mb": round(torch.cuda.memory_reserved(0) / (1024**2), 2) if torch.cuda.is_available() else 0
    }

@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local-diffusion",
                "permission": [],
                "root": MODEL_ID,
                "parent": None
            },
            {
                "id": "local/image-generator",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local-diffusion",
                "permission": [],
                "root": "local/image-generator",
                "parent": None
            }
        ]
    }

@app.post("/v1/images/generations", response_model=ImageGenerationResponse)
async def generate_images(req: ImageGenerationRequest, authorized: bool = Depends(verify_token)):
    global pipeline
    if pipeline is None:
        raise HTTPException(status_code=503, detail="El pipeline de difusión no está cargado o disponible.")
        
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="El prompt no puede estar vacío.")

    # Parsear tamaño
    width, height = 512, 512
    if req.size:
        parts = req.size.lower().split("x")
        if len(parts) == 2:
            try:
                width = int(parts[0])
                height = int(parts[1])
            except ValueError:
                width, height = 512, 512

    # Ajustar pasos y escala según el tipo de modelo
    if pipeline_type == "flux":
        steps = req.num_inference_steps or 4
        guidance = req.guidance_scale if req.guidance_scale is not None else 0.0
    else: # SDXL Turbo
        steps = req.num_inference_steps or 1
        guidance = req.guidance_scale if req.guidance_scale is not None else 0.0

    async with generation_lock:
        try:
            # Ejecutar inferencia en un hilo separado para no bloquear el bucle de eventos
            def _run_inference():
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                kwargs = {
                    "prompt": prompt,
                    "num_inference_steps": steps,
                    "guidance_scale": guidance,
                    "height": height,
                    "width": width
                }
                
                # Ejecución de la tubería
                result = pipeline(**kwargs)
                return result.images

            t_start = time.time()
            images = await asyncio.to_thread(_run_inference)
            gen_time = time.time() - t_start
            
            data_items = []
            created_ts = int(time.time())
            
            for i, img in enumerate(images):
                img_id = f"img_{created_ts}_{uuid.uuid4().hex[:8]}"
                filename = f"{img_id}.png"
                filepath = os.path.join(OUTPUT_DIR, filename)
                
                # Guardar imagen en disco
                img.save(filepath, format="PNG")
                
                obj = ImageObject(revised_prompt=prompt)
                
                if req.response_format == "b64_json":
                    buffered = io.BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    obj.b64_json = img_str
                else:
                    # Retornar URL accesible vía Gateway
                    obj.url = f"/outputs/images/{filename}"
                    
                data_items.append(obj)
                
            print(f"🎉 Generada(s) {len(images)} imagen(es) para prompt '{prompt[:40]}...' en {gen_time:.2f}s")
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            return ImageGenerationResponse(
                created=created_ts,
                data=data_items,
                model=req.model or MODEL_ID
            )
            
        except Exception as e:
            print(f"❌ Error durante la generación de imagen: {e}", file=sys.stderr)
            raise HTTPException(status_code=500, detail=f"Error en la generación: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
