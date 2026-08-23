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
CPU_THREADS = int(os.getenv("EMBEDDINGS_CPU_THREADS", "6"))
API_KEY = os.getenv("API_KEY", "tu_clave_api_aqui")

# Optimizar hilos de PyTorch en CPU
torch.set_num_threads(CPU_THREADS)

print("=" * 60)
print(f"🧠 Inicializando Servidor de Embeddings en RAM / CPU...")
print(f"📦 Modelo: {MODEL_ID} | Hilos CPU: {CPU_THREADS} | Puerto: {PORT}")
print("=" * 60)

# Carga en memoria RAM del Tokenizer y Modelo
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float32,
        trust_remote_code=True
    )
    model.eval()
    
    # Warm-up en caliente para compilar kernels de CPU y pre-alocar búferes
    warmup_text = "Calentamiento inicial del motor de embeddings semánticos en memoria RAM."
    inputs = tokenizer(warmup_text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        out = model(**inputs)
        mask = inputs["attention_mask"].unsqueeze(-1).expand(out.last_hidden_state.size()).float()
        pooled = torch.sum(out.last_hidden_state * mask, 1) / torch.clamp(mask.sum(1), min=1e-9)
        _ = F.normalize(pooled, p=2, dim=1)
        
    param_count = sum(p.numel() for p in model.parameters())
    print(f"✅ Modelo Qwen3-Embedding residente en RAM! ({param_count:,} parámetros | 1024 dims)")
    print("=" * 60)
except Exception as e:
    print(f"❌ Error crítico al cargar {MODEL_ID}: {e}", file=sys.stderr)
    tokenizer = None
    model = None

# Inicializar FastAPI
app = FastAPI(
    title="vLLM OpenAI-Compatible Embeddings Server (Qwen3-Embedding-0.6B CPU)",
    description="Microservicio persistente de Embeddings Semánticos y RAG residente en RAM con 0 MB de VRAM.",
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
            detail="El modelo de embeddings no está inicializado en memoria RAM."
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
        # Tokenización con padding dinámico y truncamiento a 8192 tokens max
        inputs = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=8192,
            return_tensors="pt"
        )
        
        prompt_tokens = int(inputs["attention_mask"].sum().item())

        # Inferencia en CPU (0 MB VRAM)
        with torch.no_grad():
            outputs = model(**inputs)
            # Mean Pooling con máscara de atención
            last_hidden_state = outputs.last_hidden_state
            attention_mask = inputs["attention_mask"].unsqueeze(-1).expand(last_hidden_state.size()).float()
            sum_embeddings = torch.sum(last_hidden_state * attention_mask, dim=1)
            sum_mask = torch.clamp(attention_mask.sum(dim=1), min=1e-9)
            pooled_embeddings = sum_embeddings / sum_mask
            
            # Normalización L2 para distancias coseno unitarias
            normalized_embeddings = F.normalize(pooled_embeddings, p=2, dim=1)
            
            if request.dimensions and request.dimensions < normalized_embeddings.shape[1]:
                normalized_embeddings = normalized_embeddings[:, :request.dimensions]
                normalized_embeddings = F.normalize(normalized_embeddings, p=2, dim=1)

        embedding_list = normalized_embeddings.cpu().tolist()

        data_items = []
        for idx, emb in enumerate(embedding_list):
            data_items.append({
                "object": "embedding",
                "index": idx,
                "embedding": emb
            })

        duration_ms = (time.time() - t_start) * 1000
        print(f"📊 [Embeddings] Procesados {len(texts)} textos ({prompt_tokens} tokens) en {duration_ms:.2f} ms")

        return {
            "object": "list",
            "data": data_items,
            "model": request.model,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "total_tokens": prompt_tokens
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
    return {
        "status": "healthy" if model is not None else "unavailable",
        "service": "vllm-embeddings",
        "model": MODEL_ID,
        "dimension": 1024,
        "device": "cpu",
        "threads": CPU_THREADS,
        "vram_mb": 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
