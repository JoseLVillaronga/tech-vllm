"""
app_embeddings_rwkv.py - Microservicio de Embeddings Semánticos de Alta Velocidad (1024D).
Basado en EmbeddingRWKV-0.4B (RWKV-7 Linear Attention) compatible con OpenAI API.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Union, Optional
import torch
import torch.nn.functional as F
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Asegurar ninja y herramientas en PATH para JIT CUDA
PROJECT_DIR = Path(__file__).resolve().parent
venv_bin = str(PROJECT_DIR / "venv" / "bin")
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

PORT = int(os.getenv("EMBEDDINGS_BACKEND_PORT", "18005"))
MODEL_PATH = os.getenv(
    "RWKV_EMBEDDINGS_MODEL_PATH",
    str(PROJECT_DIR / "lab_linear_embeddings" / "models" / "rwkv0b4-emb-curriculum.pth")
)
BATCH_SIZE = int(os.getenv("EMBEDDINGS_BATCH_SIZE", "32"))
API_KEY = os.getenv("API_KEY", "")

from rwkv_emb.model import EmbeddingRWKV
from rwkv_emb.tokenizer import RWKVTokenizer

print("=" * 65)
print("🧠 Inicializando Servidor de Embeddings Lineales (EmbeddingRWKV)...")
print(f"📦 Modelo: {MODEL_PATH}")
print(f"⚡ Puerto: {PORT} | Lote máx: {BATCH_SIZE} | Dimensiones: 1024D")
print("=" * 65)

try:
    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(f"No se encontró el checkpoint en {MODEL_PATH}")
    model = EmbeddingRWKV(MODEL_PATH)
    tokenizer = RWKVTokenizer()
    print("✅ Modelo EmbeddingRWKV cargado y operativo en GPU CUDA (1024D).")
    print("=" * 65)
except Exception as e:
    print(f"❌ Error crítico al cargar EmbeddingRWKV: {e}", file=sys.stderr)
    model = None
    tokenizer = None

app = FastAPI(
    title="vLLM OpenAI-Compatible EmbeddingRWKV Server (1024D)",
    description="Microservicio de Embeddings Semánticos de Atención Lineal compatible con OpenAI API.",
    version="2.0.0",
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
    if API_KEY and credentials:
        if credentials.credentials == API_KEY:
            return True
    return True


class EmbeddingRequest(BaseModel):
    model: str = "howard-hou/EmbeddingRWKV-0.4B"
    input: Union[str, List[str]]
    encoding_format: Optional[str] = "float"


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: List[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage


@app.get("/health", summary="Verificar estado de salud")
def health():
    if model is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado.")
    return {
        "status": "ok",
        "model": "howard-hou/EmbeddingRWKV-0.4B",
        "port": PORT,
        "dimensions": 1024,
        "device": str(model.device),
        "linear_attention": True
    }


@app.get("/v1/models", summary="Listar modelos disponibles")
def list_models():
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": "howard-hou/EmbeddingRWKV-0.4B",
                "object": "model",
                "created": now,
                "owned_by": "rwkv",
                "permission": [],
                "root": "howard-hou/EmbeddingRWKV-0.4B",
                "parent": None
            },
            {
                "id": "Qwen/Qwen3-Embedding-0.6B",
                "object": "model",
                "created": now,
                "owned_by": "compatibility-alias",
                "permission": [],
                "root": "howard-hou/EmbeddingRWKV-0.4B",
                "parent": None
            },
            {
                "id": "text-embedding-3-small",
                "object": "model",
                "created": now,
                "owned_by": "openai-alias",
                "permission": [],
                "root": "howard-hou/EmbeddingRWKV-0.4B",
                "parent": None
            },
            {
                "id": "text-embedding-ada-002",
                "object": "model",
                "created": now,
                "owned_by": "openai-alias",
                "permission": [],
                "root": "howard-hou/EmbeddingRWKV-0.4B",
                "parent": None
            }
        ]
    }


@app.post("/v1/embeddings", response_model=EmbeddingResponse, summary="Generar embeddings vectoriales")
def create_embeddings(req: EmbeddingRequest, authorized: bool = Depends(verify_token)):
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Motor de embeddings no disponible.")

    texts = [req.input] if isinstance(req.input, str) else req.input
    if not texts:
        raise HTTPException(status_code=400, detail="Input no puede estar vacío.")

    t0 = time.perf_counter()
    data_items = []
    total_tokens = 0

    with torch.no_grad():
        for idx, t in enumerate(texts):
            enc = tokenizer.encode(t.strip() if t else " ", add_eos=True)
            total_tokens += len(enc)
            emb, _ = model.forward_text_only(enc)
            norm_emb = F.normalize(emb[0].float(), p=2, dim=-1).cpu().tolist()
            data_items.append(EmbeddingData(index=idx, embedding=norm_emb))

    elapsed_ms = (time.perf_counter() - t0) * 1000
    if len(texts) > 1:
        print(f"⚡ [RWKV] {len(texts)} chunks ({total_tokens} tokens) en {elapsed_ms:.1f} ms ({elapsed_ms/len(texts):.2f} ms/chunk)")

    return EmbeddingResponse(
        data=data_items,
        model=req.model,
        usage=EmbeddingUsage(prompt_tokens=total_tokens, total_tokens=total_tokens)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_embeddings_rwkv:app", host="0.0.0.0", port=PORT, reload=False)
