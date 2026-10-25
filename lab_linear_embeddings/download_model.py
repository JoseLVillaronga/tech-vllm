"""
lab_linear_embeddings/download_model.py
Descarga controlada de modelos EmbeddingRWKV desde Hugging Face.
"""

import argparse
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download

REPO_ID = "howard-hou/EmbeddingRWKV"

MODEL_MAP = {
    "tiny": "rwkv0b1-emb-curriculum.pth",
    "base": "rwkv0b4-emb-curriculum.pth",
    "large": "rwkv1b4-emb-curriculum.pth",
    "reranker-tiny": "rwkv0b1-reranker.pth",
    "reranker-base": "rwkv0b3-reranker.pth",
    "reranker-large": "rwkv1b3-reranker.pth",
}


def download(target: str) -> Path:
    target_key = target.lower().strip()
    if target_key not in MODEL_MAP:
        raise ValueError(f"Modelo desconocido: '{target}'. Opciones válidas: {list(MODEL_MAP.keys())}")

    filename = MODEL_MAP[target_key]
    models_dir = Path(__file__).resolve().parent / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    destination = models_dir / filename

    if destination.exists():
        size_mb = destination.stat().st_size / (1024 * 1024)
        print(f"✔ Checkpoint '{filename}' ya existe localmente ({size_mb:.1f} MB) en {destination}")
        return destination

    print(f"⬇️ Descargando '{filename}' desde {REPO_ID}...")
    downloaded_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        local_dir=str(models_dir),
    )
    print(f"✅ Descarga completada: {downloaded_path}")
    return Path(downloaded_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descargador de modelos EmbeddingRWKV")
    parser.add_argument(
        "--model",
        type=str,
        default="base",
        choices=list(MODEL_MAP.keys()),
        help="Escala de modelo a descargar (default: base)",
    )
    args = parser.parse_args()
    try:
        download(args.model)
    except Exception as e:
        print(f"❌ Error durante la descarga: {e}", file=sys.stderr)
        sys.exit(1)
