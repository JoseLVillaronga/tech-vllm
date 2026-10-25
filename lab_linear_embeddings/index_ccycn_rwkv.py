"""
lab_linear_embeddings/index_ccycn_rwkv.py
Indexa los 2.967 fragmentos del CCyCN desde LanceDB producción hacia
la tabla experimental de laboratorio 'ccycn_rwkv' usando EmbeddingRWKV-0.4B.
"""

import os
import sys
import time
from pathlib import Path
import pyarrow as pa
import pyarrow.compute as pc
import lancedb
import torch
import torch.nn.functional as F

# Configurar PATH para Ninja / CUDA
venv_bin = str(Path(__file__).resolve().parent.parent / "venv" / "bin")
if venv_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{venv_bin}:{os.environ.get('PATH', '')}"

from rwkv_emb.model import EmbeddingRWKV
from rwkv_emb.tokenizer import RWKVTokenizer

PROD_DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "lancedb")
LAB_DB_PATH = str(Path(__file__).resolve().parent / "lancedb_lab")
MODEL_PATH = str(Path(__file__).resolve().parent / "models" / "rwkv0b4-emb-curriculum.pth")
CCYCN_DOC_ID = "6a9e2ee436300fe5f0afb9d9"


def main():
    print("=" * 70)
    print("🚀 INICIANDO INDEXACIÓN DEL CCyCN CON EmbeddingRWKV (1024D)")
    print(f"📂 Base origen (Lectura): {PROD_DB_PATH}")
    print(f"📂 Base destino (Lab):    {LAB_DB_PATH}")
    print("=" * 70)

    # 1. Conectar a producción en modo lectura
    prod_db = lancedb.connect(PROD_DB_PATH)
    prod_tbl = prod_db.open_table("teccam_knowledge_base")
    arrow_tbl = prod_tbl.to_arrow()

    # Filtrar por doc_id del CCyCN
    mask = pc.equal(arrow_tbl["doc_id"], CCYCN_DOC_ID)
    filtered = arrow_tbl.filter(mask)
    num_chunks = len(filtered)
    print(f"✔ Chunks del CCyCN recuperados de producción: {num_chunks}")

    if num_chunks == 0:
        print("❌ No se encontraron fragmentos para el CCyCN.")
        sys.exit(1)

    # Convertir a lista de diccionarios ordenada por chunk_index
    records = filtered.to_pylist()
    records.sort(key=lambda x: x.get("chunk_index", 0))

    # 2. Cargar modelo RWKV
    print(f"\n🧠 Cargando modelo RWKV desde {MODEL_PATH}...")
    model = EmbeddingRWKV(MODEL_PATH)
    tok = RWKVTokenizer()

    # 3. Vectorización de los 2.967 fragmentos
    print(f"⚡ Vectorizando {num_chunks} fragmentos...")
    t0 = time.perf_counter()

    new_records = []
    total_tokens = 0

    with torch.no_grad():
        for i, rec in enumerate(records):
            text_to_embed = rec.get("text", "") or rec.get("content", "")
            tokens = tok.encode(text_to_embed.strip(), add_eos=True)
            total_tokens += len(tokens)

            emb, _ = model.forward_text_only(tokens)
            norm_vec = F.normalize(emb[0].float(), p=2, dim=-1).cpu().tolist()

            rec_copy = dict(rec)
            rec_copy["vector"] = norm_vec
            new_records.append(rec_copy)

            if (i + 1) % 500 == 0 or (i + 1) == num_chunks:
                pct = ((i + 1) / num_chunks) * 100
                elapsed = time.perf_counter() - t0
                t_s = total_tokens / elapsed if elapsed > 0 else 0
                print(f"  [{i+1}/{num_chunks}] ({pct:.1f}%) - {t_s:.0f} tokens/s | Tiempo: {elapsed:.1f}s")

    elapsed_total = time.perf_counter() - t0
    print(f"✅ Vectorización completada en {elapsed_total:.2f}s ({total_tokens/elapsed_total:.0f} tokens/s promedio)")

    # 4. Guardar en base LanceDB de laboratorio
    lab_db = lancedb.connect(LAB_DB_PATH)
    table_name = "ccycn_rwkv"
    print(f"\n💾 Guardando tabla '{table_name}' en {LAB_DB_PATH}...")
    lab_tbl = lab_db.create_table(table_name, data=new_records, mode="overwrite")
    print(f"✔ Tabla creada exitosamente con {len(lab_tbl)} registros.")
    print("=" * 70)


if __name__ == "__main__":
    main()
