"""
lab_linear_embeddings/late_chunker.py
Demostración de Late Chunking en Streaming con Memoria de Estado Continuo.

Compara dos paradigmas de vectorización:
1. Early Chunking (Aislado / Ciego): El fragmento B se vectoriza sin conocer el fragmento A.
2. Streaming State Chunking: El fragmento B se vectoriza heredando el estado recurrente del fragmento A,
   resolviendo la anáfora ("el artículo anterior", "dicho defecto").
"""

import os
import sys
from pathlib import Path
import torch
import torch.nn.functional as F

# Asegurar ninja y herramientas en PATH
venv_bin = str(Path(__file__).resolve().parent.parent / "venv" / "bin")
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

from rwkv_emb.model import EmbeddingRWKV
from rwkv_emb.tokenizer import RWKVTokenizer


def cosine_sim(a: torch.Tensor, b: torch.Tensor) -> float:
    a_norm = F.normalize(a.float(), p=2, dim=-1)
    b_norm = F.normalize(b.float(), p=2, dim=-1)
    return float(torch.sum(a_norm * b_norm).item())


def run_streaming_experiment():
    model_path = str(Path(__file__).resolve().parent / "models" / "rwkv0b4-emb-curriculum.pth")
    if not Path(model_path).exists():
        print(f"❌ Modelo no encontrado en {model_path}.")
        sys.exit(1)

    print("=" * 70)
    print("🌊 EXPERIMENTO DE STREAMING STATE CHUNKING (RESOLUCIÓN DE ANÁFORAS)")
    print(f"📦 Modelo: EmbeddingRWKV-0.4B")
    print("=" * 70)

    model = EmbeddingRWKV(model_path)
    tok = RWKVTokenizer()

    # Fragmento A (Define el sujeto y el vicio)
    chunk_a = (
        "Artículo 1054 del Código Civil y Comercial de la Nación: "
        "El adquirente tiene la carga de denunciar expresamente la existencia del defecto oculto "
        "al garante dentro de los sesenta días de haberse manifestado. Si el defecto se manifiesta "
        "gradualmente, el plazo se cuenta desde que el adquirente pudo advertirlo."
    )

    # Fragmento B (Usa anáforas críticas: "esta carga", "defectos ocultos", "la responsabilidad")
    # Si se corta ciego, pierde quién es el garante y qué vicio es.
    chunk_b = (
        "El incumplimiento de la carga antes mencionada en dicho plazo legal "
        "extingue de pleno derecho toda responsabilidad por saneamiento, "
        "quedando el enajenante liberado de cualquier reclamo o acción de rescisión."
    )

    query = "¿Qué consecuencia produce no denunciar el vicio oculto al garante en el plazo de sesenta días?"

    tokens_a = tok.encode(chunk_a, add_eos=True)
    tokens_b = tok.encode(chunk_b, add_eos=True)
    tokens_q = tok.encode(query, add_eos=True)

    with torch.no_grad():
        # Consulta
        emb_q, _ = model.forward_text_only(tokens_q)

        # 1. Early Chunking (Vectorización Aislada)
        emb_b_isolated, _ = model.forward_text_only(tokens_b)

        # 2. Streaming State Chunking (Vectorización encadenada con herencia de estado)
        _, state_after_a = model.forward_text_only(tokens_a)
        emb_b_streamed, _ = model.forward_text_only(tokens_b, state=state_after_a)

    sim_isolated = cosine_sim(emb_q[0], emb_b_isolated[0])
    sim_streamed = cosine_sim(emb_q[0], emb_b_streamed[0])
    delta = sim_streamed - sim_isolated

    print(f"Fragmento A (Antecedente): \"{chunk_a[:60]}...\"")
    print(f"Fragmento B (Consecuente):  \"{chunk_b[:60]}...\"")
    print(f"Consulta evaluada:        \"{query}\"\n")
    print("-" * 70)
    print(f"1. Similitud Chunk B AISLADO (Early Chunking tradicional):  {sim_isolated:.4f}")
    print(f"2. Similitud Chunk B STREAMED (Con estado latente de A):    {sim_streamed:.4f}")
    print(f"📈 Ganancia de fidelidad semántica por memoria de estado:    {delta:+.4f} ({delta/sim_isolated*100:+.2f}%)")
    print("-" * 70)

    if delta > 0:
        print("✔ HIPÓTESIS CONFIRMADA: El estado recurrente inyectó el contexto del artículo anterior en el fragmento B.")
    else:
        print("ℹ️ La herencia de estado no produjo ganancia en este par específico.")
    print("=" * 70)


if __name__ == "__main__":
    run_streaming_experiment()
