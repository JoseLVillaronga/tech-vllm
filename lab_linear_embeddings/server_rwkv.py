"""
lab_linear_embeddings/server_rwkv.py
Microservicio FastAPI compatible con OpenAI Embeddings API (:18055).
Sirve EmbeddingRWKV-0.4B (1024D) de manera totalmente aislada de producción.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Union, Optional
import torch
import torch.nn.functional as F
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Asegurar ninja y herramientas en PATH
venv_bin = str(Path(__file__).resolve().parent.parent / "venv" / "bin")
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

from rwkv_emb.model import EmbeddingRWKV
from rwkv_emb.tokenizer import RWKVTokenizer

PORT = int(os.getenv("LAB_EMBEDDINGS_PORT", "18055"))
MODEL_PATH = str(Path(__file__).resolve().parent / "models" / "rwkv0b4-emb-curriculum.pth")

app = FastAPI(
    title="Lab EmbeddingRWKV Server (1024D)",
    description="Microservicio de pruebas aislado para embeddings lineales RWKV-7.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model: Optional[EmbeddingRWKV] = None
tokenizer: Optional[RWKVTokenizer] = None


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


@app.on_event("startup")
def startup_event():
    global model, tokenizer
    if not Path(MODEL_PATH).exists():
        raise RuntimeError(f"Modelo no encontrado en {MODEL_PATH}. Ejecuta download_model.py primero.")
    print(f"🧠 [Lab Server] Cargando EmbeddingRWKV desde {MODEL_PATH}...")
    model = EmbeddingRWKV(MODEL_PATH)
    tokenizer = RWKVTokenizer()
    print(f"✅ [Lab Server] Operativo en puerto :{PORT} (Dimensiones: 1024D)")


@app.get("/health")
def health():
    return {"status": "ok", "model": "EmbeddingRWKV-0.4B", "port": PORT, "dimensions": 1024}


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def create_embeddings(req: EmbeddingRequest):
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Modelo no inicializado.")

    inputs = [req.input] if isinstance(req.input, str) else req.input
    if not inputs:
        raise HTTPException(status_code=400, detail="Input no puede estar vacío.")

    data_items = []
    total_tokens = 0

    with torch.no_grad():
        for idx, text in enumerate(inputs):
            tokens = tokenizer.encode(text.strip(), add_eos=True)
            total_tokens += len(tokens)
            emb, _ = model.forward_text_only(tokens)
            # L2 normalize para similitud coseno canónica
            norm_emb = F.normalize(emb[0].float(), p=2, dim=-1)
            data_items.append(EmbeddingData(
                index=idx,
                embedding=norm_emb.cpu().tolist()
            ))

    return EmbeddingResponse(
        data=data_items,
        model=req.model,
        usage=EmbeddingUsage(prompt_tokens=total_tokens, total_tokens=total_tokens)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server_rwkv:app", host="0.0.0.0", port=PORT, reload=False)
