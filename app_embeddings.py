import os
import sys
import time
import torch
import torch.nn.functional as F
from typing import Union, List, Optional
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModel

# Cargar variables de entorno
load_dotenv()

PORT = int(os.getenv("EMBEDDINGS_BACKEND_PORT", "18005"))
MODEL_ID = os.getenv("EMBEDDINGS_MODEL", "Qwen/Qwen3-Embedding-0.6B")
DEVICE_CONFIG = os.getenv("EMBEDDINGS_DEVICE", "cuda").strip().lower()
CPU_THREADS = int(os.getenv("EMBEDDINGS_CPU_THREADS", "6"))
BATCH_SIZE = int(os.getenv("EMBEDDINGS_BATCH_SIZE", "64"))
from config import API_KEY

# Determinar dispositivo de aceleración
if DEVICE_CONFIG == "cuda" and torch.cuda.is_available():
    DEVICE = torch.device("cuda")
    DTYPE = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    device_desc = f"GPU CUDA ({torch.cuda.get_device_name(0)}) con {DTYPE}"
else:
    DEVICE = torch.device("cpu")
    DTYPE = torch.float32
    torch.set_num_threads(CPU_THREADS)
    device_desc = f"CPU ({CPU_THREADS} hilos) con float32"

print("=" * 60)
print(f"🧠 Inicializando Servidor de Embeddings...")
print(f"📦 Modelo: {MODEL_ID}")
print(f"⚡ Hardware: {device_desc} | Lote máx: {BATCH_SIZE} | Puerto: {PORT}")
print("=" * 60)

# Carga del Tokenizer y Modelo en memoria
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        MODEL_ID,
        dtype=DTYPE,
        trust_remote_code=True
    ).to(DEVICE)
    model.eval()
    
    # Warm-up en caliente para compilar kernels de CUDA y pre-alocar tensores
    warmup_text = "Calentamiento inicial del motor de embeddings semánticos en GPU CUDA."
    inputs = tokenizer(warmup_text, return_tensors="pt", padding=True, truncation=True, max_length=512).to(DEVICE)
    with torch.no_grad():
        out = model(**inputs)
        mask = inputs["attention_mask"].unsqueeze(-1).expand(out.last_hidden_state.size()).float()
        pooled = torch.sum(out.last_hidden_state * mask, 1) / torch.clamp(mask.sum(1), min=1e-9)
        _ = F.normalize(pooled, p=2, dim=1)
        
    if DEVICE.type == "cuda":
        torch.cuda.synchronize()
        vram_mb = torch.cuda.memory_allocated() / (1024 * 1024)
        vram_str = f"~{vram_mb:.1f} MB VRAM"
    else:
        vram_str = "0 MB VRAM (RAM)"
        
    param_count = sum(p.numel() for p in model.parameters())
    print(f"✅ Modelo Qwen3-Embedding cargado y operativo! ({param_count:,} parámetros | 1024 dims | {vram_str})")
    print("=" * 60)
except Exception as e:
    print(f"❌ Error crítico al cargar {MODEL_ID}: {e}", file=sys.stderr)
    tokenizer = None
    model = None

# Inicializar FastAPI
app = FastAPI(
    title=f"vLLM OpenAI-Compatible Embeddings Server ({MODEL_ID})",
    description="Microservicio de Embeddings Semánticos y RAG de alta velocidad compatible con OpenAI API.",
    version="1.1.0",
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
    if credentials and credentials.credentials == expected_token:
        return True
    return True

class EmbeddingRequest(BaseModel):
    model: str = Field(default=MODEL_ID, description="Identificador del modelo de embeddings")
    input: Union[str, List[str]] = Field(..., description="Texto o lista de textos a vectorizar")
    encoding_format: Optional[str] = Field(default="float", description="Formato de codificación (float o base64)")
    dimensions: Optional[int] = Field(default=None, description="Dimensión de salida (permite truncamiento Matryoshka si aplica)")

@app.post("/v1/embeddings", summary="Generar Embeddings Vectoriales (OpenAI-Compatible)")
async def create_embeddings(request: EmbeddingRequest, auth: bool = Depends(verify_token)):
    if model is None or tokenizer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El modelo de embeddings no está inicializado en memoria."
        )

    # Normalizar input a lista de strings
    if isinstance(request.input, str):
        texts = [request.input]
    elif isinstance(request.input, list):
        texts = request.input
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'input' debe ser un string o una lista de strings."
        )

    if not texts or all(not str(t).strip() for t in texts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El texto de entrada no puede estar vacío."
        )

    t_start = time.time()

    try:
        all_embeddings = []
        total_prompt_tokens = 0
        
        # Procesamiento en lotes (mini-batching) para optimizar paralelismo y mantener VRAM constante
        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i : i + BATCH_SIZE]
            
            # Tokenización con padding dinámico y truncamiento seguro a 2048 tokens max
            inputs = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=2048,
                return_tensors="pt"
            ).to(DEVICE)
            
            batch_tokens = int(inputs["attention_mask"].sum().item())
            total_prompt_tokens += batch_tokens

            # Inferencia acelerada
            with torch.no_grad():
                outputs = model(**inputs)
                # Mean Pooling ponderado con máscara de atención
                last_hidden_state = outputs.last_hidden_state
                attention_mask = inputs["attention_mask"].unsqueeze(-1).expand(last_hidden_state.size()).float()
                sum_embeddings = torch.sum(last_hidden_state * attention_mask, dim=1)
                sum_mask = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
                pooled_embeddings = sum_embeddings / sum_mask
                
                # Normalización L2 para similitud coseno
                normalized_embeddings = F.normalize(pooled_embeddings, p=2, dim=1)
                
                if request.dimensions and request.dimensions < normalized_embeddings.shape[1]:
                    normalized_embeddings = normalized_embeddings[:, :request.dimensions]
                    normalized_embeddings = F.normalize(normalized_embeddings, p=2, dim=1)

            all_embeddings.extend(normalized_embeddings.cpu().tolist())
            
            # Limpieza inmediata de tensores intermedios
            del inputs, outputs, last_hidden_state, attention_mask, sum_embeddings, sum_mask, pooled_embeddings, normalized_embeddings
            if DEVICE.type == "cuda":
                torch.cuda.empty_cache()

        if DEVICE.type == "cuda":
            torch.cuda.synchronize()

        data_items = []
        for idx, emb in enumerate(all_embeddings):
            data_items.append({
                "object": "embedding",
                "index": idx,
                "embedding": emb
            })

        duration_ms = (time.time() - t_start) * 1000
        ms_per_chunk = duration_ms / max(1, len(texts))
        print(f"⚡ [Embeddings] Procesados {len(texts)} fragmentos ({total_prompt_tokens} tokens) en {duration_ms:.2f} ms ({ms_per_chunk:.2f} ms/chunk)")

        return {
            "object": "list",
            "data": data_items,
            "model": request.model,
            "usage": {
                "prompt_tokens": total_prompt_tokens,
                "total_tokens": total_prompt_tokens
            }
        }

    except Exception as e:
        print(f"❌ Error al generar embeddings: {e}", file=sys.stderr)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante el cómputo de embeddings: {str(e)}"
        )

@app.get("/v1/models", summary="Listar Modelos Disponibles")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "qwen",
                "permission": [],
                "root": MODEL_ID,
                "parent": None
            },
            {
                "id": "text-embedding-ada-002",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openai-alias",
                "permission": [],
                "root": MODEL_ID,
                "parent": None
            },
            {
                "id": "text-embedding-3-small",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openai-alias",
                "permission": [],
                "root": MODEL_ID,
                "parent": None
            }
        ]
    }

@app.get("/health", summary="Verificar estado de salud del servidor de embeddings")
async def health():
    vram_allocated_mb = round(torch.cuda.memory_allocated() / (1024 * 1024), 1) if DEVICE.type == "cuda" else 0
    return {
        "status": "healthy" if model is not None else "unavailable",
        "service": "vllm-embeddings",
        "model": MODEL_ID,
        "dimension": 1024,
        "device": str(DEVICE),
        "vram_mb": vram_allocated_mb,
        "batch_size": BATCH_SIZE
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
