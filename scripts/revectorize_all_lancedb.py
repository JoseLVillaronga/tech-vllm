"""
scripts/revectorize_all_lancedb.py
Re-vectorización masiva y atómica de las dos bases LanceDB de producción:
1. 'teccam_knowledge_base' (32.117 chunks)
2. 'kb_tech_support_argentina' (31.653 chunks)
Utilizando EmbeddingRWKV-0.4B (1024D).
"""

import os
import sys
import time
from pathlib import Path
import lancedb
import pyarrow as pa
import torch
import torch.nn.functional as F

# Configurar PATH para Ninja / CUDA
PROJECT_DIR = Path(__file__).resolve().parent.parent
venv_bin = str(PROJECT_DIR / "venv" / "bin")
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

from rwkv_emb.model import EmbeddingRWKV
from rwkv_emb.tokenizer import RWKVTokenizer

LANCEDB_PATH = str(PROJECT_DIR / "data" / "lancedb")
MODEL_PATH = str(PROJECT_DIR / "lab_linear_embeddings" / "models" / "rwkv0b4-emb-curriculum.pth")
TABLES_TO_PROCESS = ["teccam_knowledge_base", "kb_tech_support_argentina"]


def revectorize_table(db, table_name: str, model: EmbeddingRWKV, tok: RWKVTokenizer):
    print("\n" + "=" * 70)
    print(f"📦 Procesando tabla: '{table_name}'")
    print("=" * 70)

    try:
        tbl = db.open_table(table_name)
    except Exception as e:
        print(f"❌ Error al abrir tabla '{table_name}': {e}")
        return False

    arrow_tbl = tbl.to_arrow()
    total_records = len(arrow_tbl)
    print(f"✔ Registros cargados en memoria: {total_records:,}")

    if total_records == 0:
        print(f"⚠️ La tabla '{table_name}' está vacía. Omitiendo.")
        return True

    records = arrow_tbl.to_pylist()

    t0 = time.perf_counter()
    total_tokens = 0
    updated_records = []

    with torch.no_grad():
        for i, rec in enumerate(records):
            text = rec.get("text", "") or rec.get("content", "")
            enc = tok.encode(text.strip() if text else " ", add_eos=True)
            total_tokens += len(enc)

            emb, _ = model.forward_text_only(enc)
            norm_emb = F.normalize(emb[0].float(), p=2, dim=-1).cpu().tolist()

            rec_copy = dict(rec)
            rec_copy["vector"] = norm_emb
            updated_records.append(rec_copy)

            # Telemetría periódica cada 1.000 chunks
            current_done = i + 1
            if current_done % 1000 == 0 or current_done == total_records:
                elapsed = time.perf_counter() - t0
                pct = (current_done / total_records) * 100
                rate = current_done / elapsed if elapsed > 0 else 0
                tok_s = total_tokens / elapsed if elapsed > 0 else 0
                remaining_s = (total_records - current_done) / rate if rate > 0 else 0
                print(f"  ⚡ [{current_done:,}/{total_records:,}] ({pct:5.1f}%) | {tok_s:5.0f} tok/s | ETA: {remaining_s:4.0f}s ({remaining_s/60:.1f}m)")

    elapsed_total = time.perf_counter() - t0
    print(f"✅ Vectorización de '{table_name}' completada en {elapsed_total:.1f}s ({elapsed_total/60:.1f}m) a {total_tokens/elapsed_total:.0f} tok/s promedio.")

    # Escritura atómica
    print(f"💾 Escribiendo {len(updated_records):,} registros en LanceDB...")
    db.create_table(table_name, data=updated_records, mode="overwrite")
    print(f"✔ Tabla '{table_name}' re-indexada con éxito.")
    return True


def main():
    print("=" * 70)
    print("🚀 INICIANDO RE-VECTORIZACIÓN COMPLETA DE LANCEDB (EmbeddingRWKV 1024D)")
    print(f"📂 LanceDB Path: {LANCEDB_PATH}")
    print(f"🧠 Modelo:       {MODEL_PATH}")
    print("=" * 70)

    if not Path(MODEL_PATH).exists():
        print(f"❌ Checkpoint no encontrado en {MODEL_PATH}")
        sys.exit(1)

    db = lancedb.connect(LANCEDB_PATH)
    model = EmbeddingRWKV(MODEL_PATH)
    tok = RWKVTokenizer()

    t_global = time.perf_counter()
    for tbl_name in TABLES_TO_PROCESS:
        success = revectorize_table(db, tbl_name, model, tok)
        if not success:
            print(f"❌ Falló la re-vectorización de '{tbl_name}'. Abortando.")
            sys.exit(1)

    t_total = time.perf_counter() - t_global
    print("\n" + "=" * 70)
    print(f"🎉 TODAS LAS TABLAS HAN SIDO RE-VECTORIZADAS EXITOSAMENTE EN {t_total:.1f}s ({t_total/60:.2f} min)")
    print("=" * 70)


if __name__ == "__main__":
    main()
