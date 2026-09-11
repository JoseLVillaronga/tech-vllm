"""
rag.embeddings - Generación de embeddings vectoriales (1024-dim) con cliente HTTP y mitigación Anti-OOM adaptativa.
"""

import sys
import time
from typing import List
import httpx
from .config import EMBEDDINGS_BACKEND_PORT, MASTER_KEY


def generate_embedding(text: str, timeout: float = 15.0) -> List[float]:
    """Genera un vector embedding de 1024 dimensiones llamando al microservicio vllm-embeddings."""
    url = f"http://127.0.0.1:{EMBEDDINGS_BACKEND_PORT}/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {MASTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "input": text.strip()
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["data"][0]["embedding"]
            else:
                raise RuntimeError(f"Error HTTP {resp.status_code} desde vllm-embeddings: {resp.text}")
    except Exception as e:
        print(f"❌ [RAG Engine] Error generando embedding: {e}", file=sys.stderr)
        raise


def generate_embeddings_batch(texts: List[str], batch_size: int = 6, timeout: float = 30.0) -> List[List[float]]:
    """
    Genera embeddings en lotes seguros llamando al microservicio vllm-embeddings.
    Incluye reducción adaptativa de tamaño de lote (Anti-OOM) y reintento automático si hay picos de VRAM.
    """
    if not texts:
        return []
    url = f"http://127.0.0.1:{EMBEDDINGS_BACKEND_PORT}/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {MASTER_KEY}",
        "Content-Type": "application/json"
    }
    
    all_embeddings = []
    with httpx.Client(timeout=timeout) as client:
        i = 0
        curr_batch_size = min(batch_size, 6)
        while i < len(texts):
            batch_slice = texts[i : i + curr_batch_size]
            payload = {
                "model": "Qwen/Qwen3-Embedding-0.6B",
                "input": batch_slice
            }
            try:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                    all_embeddings.extend([item["embedding"] for item in items])
                    i += len(batch_slice)
                    # Restaurar batch size normal progresivamente sin exceder batch_size
                    if curr_batch_size < batch_size:
                        curr_batch_size = min(batch_size, curr_batch_size + 1)
                else:
                    raise RuntimeError(f"Error HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                # Si falló (ej: CUDA OOM por fragmentos densos), reducir a la mitad y reintentar
                if curr_batch_size > 1:
                    curr_batch_size = max(1, curr_batch_size // 2)
                    print(f"⚠️ [RAG Engine] Reduciendo lote a {curr_batch_size} chunks por presión de VRAM y reintentando...", file=sys.stderr)
                    time.sleep(0.3)
                else:
                    print(f"❌ [RAG Engine] Error irrecuperable en chunk {i}: {e}", file=sys.stderr)
                    raise
                    
    return all_embeddings


__all__ = [
    "generate_embedding",
    "generate_embeddings_batch"
]
