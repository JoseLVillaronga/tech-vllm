"""
lab_linear_embeddings/bench_retrieval.py
Evaluación comparativa A/B de fidelidad semántica en español:
EmbeddingRWKV-0.4B (1024D) vs. Qwen3-Embedding-0.6B (:18005)
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import torch
import torch.nn.functional as F
import httpx

# Asegurar ninja y herramientas en PATH
venv_bin = str(Path(__file__).resolve().parent.parent / "venv" / "bin")
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

from rwkv_emb.model import EmbeddingRWKV
from rwkv_emb.tokenizer import RWKVTokenizer

QWEN_URL = "http://127.0.0.1:18005/v1/embeddings"


def cosine_sim(a: torch.Tensor, b: torch.Tensor) -> float:
    a_norm = F.normalize(a.float(), p=2, dim=-1)
    b_norm = F.normalize(b.float(), p=2, dim=-1)
    return float(torch.sum(a_norm * b_norm).item())


def get_qwen_embedding(text: str) -> Optional[torch.Tensor]:
    try:
        resp = httpx.post(
            QWEN_URL,
            json={"model": "Qwen/Qwen3-Embedding-0.6B", "input": text.strip()},
            timeout=10.0
        )
        if resp.status_code == 200:
            vec = resp.json()["data"][0]["embedding"]
            return torch.tensor(vec, dtype=torch.float32)
        else:
            return None
    except Exception as e:
        print(f"⚠️ [Qwen3 HTTP] Error al consultar :18005: {e}")
        return None


def get_rwkv_embedding(model: EmbeddingRWKV, tok: RWKVTokenizer, text: str) -> torch.Tensor:
    tokens = tok.encode(text.strip(), add_eos=True)
    with torch.no_grad():
        emb, _ = model.forward_text_only(tokens)
    return emb[0].float()


def run_benchmark():
    data_path = Path(__file__).resolve().parent / "data" / "test_queries.json"
    with open(data_path, "r", encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    model_path = str(Path(__file__).resolve().parent / "models" / "rwkv0b4-emb-curriculum.pth")
    if not Path(model_path).exists():
        print(f"❌ Modelo no encontrado en {model_path}. Ejecuta download_model.py primero.")
        sys.exit(1)

    print("=" * 70)
    print("🔬 INICIANDO BENCHMARK DE RECUPERACIÓN SEMÁNTICA (A/B ESPAÑOL)")
    print(f"📦 Modelo A (Producción): Qwen3-Embedding-0.6B (vía :18005)")
    print(f"📦 Modelo B (Experimental): EmbeddingRWKV-0.4B (1024D)")
    print(f"📋 Casos de prueba: {len(dataset)} pares (Jurídicos CCyCN / Infoleg + Técnicos Teccam)")
    print("=" * 70)

    # Cargar RWKV
    rwkv_model = EmbeddingRWKV(model_path)
    rwkv_tok = RWKVTokenizer()

    # Verificar disponibilidad de Qwen
    test_qwen = get_qwen_embedding("Test de conexión")
    has_qwen = test_qwen is not None
    if not has_qwen:
        print("⚠️ Qwen3 no respondió en :18005. Se evaluará únicamente EmbeddingRWKV.\n")

    results = []
    rwkv_correct = 0
    qwen_correct = 0

    for i, item in enumerate(dataset, start=1):
        q = item["query"]
        pos = item["positive_passage"]
        dist = item["distractor_passage"]

        # RWKV
        rwkv_q = get_rwkv_embedding(rwkv_model, rwkv_tok, q)
        rwkv_pos = get_rwkv_embedding(rwkv_model, rwkv_tok, pos)
        rwkv_dist = get_rwkv_embedding(rwkv_model, rwkv_tok, dist)

        sim_rwkv_pos = cosine_sim(rwkv_q, rwkv_pos)
        sim_rwkv_dist = cosine_sim(rwkv_q, rwkv_dist)
        margin_rwkv = sim_rwkv_pos - sim_rwkv_dist
        rwkv_hit = margin_rwkv > 0
        if rwkv_hit:
            rwkv_correct += 1

        # Qwen3
        sim_qwen_pos = 0.0
        sim_qwen_dist = 0.0
        margin_qwen = 0.0
        qwen_hit = False

        if has_qwen:
            qwen_q = get_qwen_embedding(q)
            qwen_pos = get_qwen_embedding(pos)
            qwen_dist = get_qwen_embedding(dist)
            if qwen_q is not None and qwen_pos is not None and qwen_dist is not None:
                sim_qwen_pos = cosine_sim(qwen_q, qwen_pos)
                sim_qwen_dist = cosine_sim(qwen_q, qwen_dist)
                margin_qwen = sim_qwen_pos - sim_qwen_dist
                qwen_hit = margin_qwen > 0
                if qwen_hit:
                    qwen_correct += 1

        results.append({
            "id": item["id"],
            "rwkv": {"pos": sim_rwkv_pos, "dist": sim_rwkv_dist, "margin": margin_rwkv, "hit": rwkv_hit},
            "qwen": {"pos": sim_qwen_pos, "dist": sim_qwen_dist, "margin": margin_qwen, "hit": qwen_hit} if has_qwen else None
        })

        print(f"\n[{i}/{len(dataset)}] ID: {item['id']} ({item['category']})")
        print(f"  Consulta: \"{q[:70]}...\"")
        print(f"  ⚡ EmbeddingRWKV-0.4B: Sim Pos={sim_rwkv_pos:.4f} | Sim Dist={sim_rwkv_dist:.4f} | Margen={margin_rwkv:+.4f} | {'✔ HIT' if rwkv_hit else '❌ MISS'}")
        if has_qwen:
            print(f"  🧠 Qwen3-Embedding:   Sim Pos={sim_qwen_pos:.4f} | Sim Dist={sim_qwen_dist:.4f} | Margen={margin_qwen:+.4f} | {'✔ HIT' if qwen_hit else '❌ MISS'}")

    total = len(dataset)
    print("\n" + "=" * 70)
    print("📊 RESUMEN FINAL DEL BENCHMARK")
    print(f"• EmbeddingRWKV-0.4B Precisión Top-1: {rwkv_correct}/{total} ({rwkv_correct/total*100:.1f}%)")
    if has_qwen:
        print(f"• Qwen3-Embedding-0.6B Precisión Top-1: {qwen_correct}/{total} ({qwen_correct/total*100:.1f}%)")
    print("=" * 70)


if __name__ == "__main__":
    Optional_Tensor = Any
    run_benchmark()
