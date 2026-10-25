"""
lab_linear_embeddings/bench_memory_speed.py
Medición empírica de velocidad de prefill (tokens/s) y huella de VRAM
en secuencias de longitud creciente (hasta 32k tokens) con EmbeddingRWKV-0.4B.
"""

import os
import sys
import time
from pathlib import Path
import torch

# Asegurar ninja y herramientas en PATH
venv_bin = str(Path(__file__).resolve().parent.parent / "venv" / "bin")
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

from rwkv_emb.model import EmbeddingRWKV
from rwkv_emb.tokenizer import RWKVTokenizer


def benchmark_lengths():
    model_path = str(Path(__file__).resolve().parent / "models" / "rwkv0b4-emb-curriculum.pth")
    if not Path(model_path).exists():
        print(f"❌ Modelo no encontrado en {model_path}.")
        sys.exit(1)

    print("=" * 70)
    print("⚡ BENCHMARK DE VELOCIDAD DE PREFILL Y CONSUMO DE VRAM")
    print(f"📦 Modelo: EmbeddingRWKV-0.4B (1024D)")
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    print(f"🖥️ Dispositivo: {device_name}")
    print("=" * 70)

    model = EmbeddingRWKV(model_path)
    tok = RWKVTokenizer()

    # Fragmento representativo en español (CCyCN)
    base_paragraph = (
        "Artículo 1054 del Código Civil y Comercial de la Nación Argentina: "
        "El adquirente tiene la carga de denunciar expresamente la existencia del defecto oculto "
        "al garante dentro de los sesenta días de haberse manifestado. Si el defecto se manifiesta "
        "gradualmente, el plazo se cuenta desde que el adquirente pudo advertirlo. "
        "El incumplimiento de esta carga extingue la responsabilidad por defectos ocultos. "
    )
    base_tokens = tok.encode(base_paragraph, add_eos=False)
    print(f"Token base por párrafo: {len(base_tokens)} tokens\n")

    test_lengths = [512, 2048, 4096, 8192, 16384, 32768]

    # Warmup
    print("🔥 Realizando warmup inicial...")
    warmup_tokens = base_tokens[:64] + [65535]
    with torch.no_grad():
        _ = model.forward_text_only(warmup_tokens)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()

    print(f"{'Tokens':>8} | {'Tiempo (ms)':>12} | {'Velocidad (tok/s)':>18} | {'VRAM Pico (MB)':>15}")
    print("-" * 62)

    for target_len in test_lengths:
        repeats = (target_len // len(base_tokens)) + 1
        stream = (base_tokens * repeats)[:target_len - 1] + [65535]
        actual_len = len(stream)

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()

        start_t = time.perf_counter()
        with torch.no_grad():
            emb, state = model.forward_text_only(stream)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024)
        else:
            peak_vram = 0.0

        elapsed = time.perf_counter() - start_t
        tokens_per_sec = actual_len / elapsed if elapsed > 0 else 0
        elapsed_ms = elapsed * 1000

        print(f"{actual_len:>8} | {elapsed_ms:>11.1f} ms | {tokens_per_sec:>16.0f} t/s | {peak_vram:>13.1f} MB")

    print("-" * 62)
    print("✔ Benchmark completado con éxito.")


if __name__ == "__main__":
    benchmark_lengths()
