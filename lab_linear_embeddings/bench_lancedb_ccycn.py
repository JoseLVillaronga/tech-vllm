"""
lab_linear_embeddings/bench_lancedb_ccycn.py
Harness de evaluación A/B masiva en LanceDB sobre los 2.967 fragmentos del CCyCN:
Qwen3-Embedding-0.6B (Producción) vs. EmbeddingRWKV-0.4B (Laboratorio)
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
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
QWEN_URL = "http://127.0.0.1:18005/v1/embeddings"

QUERIES = [
    {
        "id": "vicios_redhibitorios",
        "tema": "Contratos / Garantías",
        "query": "¿Cuál es el plazo para denunciar la existencia de un vicio o defecto oculto en cosas muebles?",
        "target_art": "1054",
        "keywords": ["1054", "sesenta días", "defecto oculto"]
    },
    {
        "id": "prescripcion_danos",
        "tema": "Responsabilidad Civil",
        "query": "¿En qué plazo prescribe la acción indemnizatoria de daños derivados de la responsabilidad civil extracontractual?",
        "target_art": "2561",
        "keywords": ["2561", "tres años", "responsabilidad civil"]
    },
    {
        "id": "prescripcion_nulidad",
        "tema": "Actos Jurídicos",
        "query": "¿Cuál es el plazo de prescripción para pedir la nulidad relativa o revisión por lesión o vicios de la voluntad?",
        "target_art": "2562",
        "keywords": ["2562", "dos años", "nulidad"]
    },
    {
        "id": "locacion_resolucion_anticipada",
        "tema": "Contratos / Locación",
        "query": "¿Cuándo puede el locatario resolver anticipadamente el contrato de locación habitacional?",
        "target_art": "1221",
        "keywords": ["1221", "resolver", "locatario"]
    },
    {
        "id": "leasing_opcion_compra",
        "tema": "Contratos / Leasing",
        "query": "¿En qué momento puede el tomador ejercer la opción de compra en el contrato de leasing?",
        "target_art": "1240",
        "keywords": ["1240", "opción de compra", "tres cuartas partes"]
    },
    {
        "id": "sena_confirmatoria",
        "tema": "Contratos / Disposiciones Generales",
        "query": "¿Cuál es la regla supletoria respecto a la seña en los contratos: es confirmatoria o faculta el arrepentimiento?",
        "target_art": "1059",
        "keywords": ["1059", "seña", "confirmatoria"]
    },
    {
        "id": "compensacion_economica_caducidad",
        "tema": "Derecho de Familia / Divorcio",
        "query": "¿Cuál es el plazo de caducidad para pedir la compensación económica tras la sentencia de divorcio?",
        "target_art": "442",
        "keywords": ["442", "seis meses", "compensación económica"]
    },
    {
        "id": "alimentos_hijos_mayores_estudios",
        "tema": "Responsabilidad Parental",
        "query": "¿Hasta qué edad subsiste la obligación de alimentos de los progenitores si el hijo mayor estudia o se capacita?",
        "target_art": "663",
        "keywords": ["663", "veinticinco años", "estudios"]
    },
    {
        "id": "simulacion_contraescritura",
        "tema": "Actos Jurídicos / Simulación",
        "query": "¿Qué recaudo o instrumento se exige a las partes otorgantes para ejercer la acción de simulación?",
        "target_art": "335",
        "keywords": ["335", "contradocumento", "simulación"]
    },
    {
        "id": "fraude_inoponibilidad",
        "tema": "Actos Jurídicos / Fraude",
        "query": "¿Cuáles son los requisitos para que prospere la declaración de inoponibilidad por fraude a los acreedores?",
        "target_art": "339",
        "keywords": ["339", "inoponibilidad", "fraude", "insolvencia"]
    },
    {
        "id": "regimen_patrimonial_cambio",
        "tema": "Matrimonio / Régimen Patrimonial",
        "query": "¿Cuándo y por qué medio pueden los cónyuges modificar el régimen patrimonial de comunidad a separación de bienes?",
        "target_art": "449",
        "keywords": ["449", "convención", "un año", "escritura pública"]
    },
    {
        "id": "usucapion_breve",
        "tema": "Derechos Reales / Prescripción",
        "query": "¿Cuáles son los requisitos de plazo, justo título y buena fe para la prescripción adquisitiva breve de inmuebles?",
        "target_art": "1898",
        "keywords": ["1898", "diez años", "justo título", "buena fe"]
    },
    {
        "id": "privilegio_hipotecario",
        "tema": "Privilegios y Garantías",
        "query": "¿Qué extensión y privilegio especial tiene el crédito garantizado con hipoteca sobre el inmueble gravado?",
        "target_art": "2582",
        "keywords": ["2582", "hipotecario", "privilegio especial"]
    },
    {
        "id": "legitima_descendientes",
        "tema": "Derecho Sucesorio",
        "query": "¿Cuál es la porción legítima que la ley reserva a los descendientes en la sucesión testamentaria?",
        "target_art": "2445",
        "keywords": ["2445", "dos tercios", "descendientes", "porción legítima"]
    },
    {
        "id": "caso_fortuito_fuerza_mayor",
        "tema": "Obligaciones / Responsabilidad",
        "query": "¿Cómo define el código al caso fortuito o fuerza mayor como eximente de responsabilidad?",
        "target_art": "1730",
        "keywords": ["1730", "caso fortuito", "fuerza mayor", "imprevisible"]
    }
]


def get_qwen_embedding(text: str) -> Optional[List[float]]:
    try:
        resp = httpx.post(
            QWEN_URL,
            json={"model": "Qwen/Qwen3-Embedding-0.6B", "input": text.strip()},
            timeout=15.0
        )
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"⚠️ Error conectando a Qwen3 (:18005): {e}")
    return None


def get_rwkv_embedding(model: EmbeddingRWKV, tok: RWKVTokenizer, text: str) -> List[float]:
    tokens = tok.encode(text.strip(), add_eos=True)
    with torch.no_grad():
        emb, _ = model.forward_text_only(tokens)
    norm_vec = F.normalize(emb[0].float(), p=2, dim=-1)
    return norm_vec.cpu().tolist()


def evaluate():
    print("=" * 75)
    print("⚖️ BENCHMARK DE RECUPERACIÓN REAL EN LANCEDB (2.967 CHUNKS DEL CCyCN)")
    print("=" * 75)

    # Conectar tablas
    prod_db = lancedb.connect(PROD_DB_PATH)
    prod_tbl = prod_db.open_table("teccam_knowledge_base")

    lab_db = lancedb.connect(LAB_DB_PATH)
    lab_tbl = lab_db.open_table("ccycn_rwkv")

    # Cargar RWKV
    rwkv_model = EmbeddingRWKV(MODEL_PATH)
    rwkv_tok = RWKVTokenizer()

    # Verificar Qwen
    has_qwen = get_qwen_embedding("test") is not None
    if not has_qwen:
        print("❌ Qwen3 no responde en :18005. Abortando.")
        sys.exit(1)

    qwen_top1 = 0
    qwen_top3 = 0
    rwkv_top1 = 0
    rwkv_top3 = 0

    print(f"\nEjecutando {len(QUERIES)} consultas jurídicas de alta especificidad...\n")

    for idx, q_info in enumerate(QUERIES, start=1):
        q_text = q_info["query"]
        target = q_info["target_art"]
        kws = q_info["keywords"]

        # Vectores
        qwen_vec = get_qwen_embedding(q_text)
        rwkv_vec = get_rwkv_embedding(rwkv_model, rwkv_tok, q_text)

        # Búsqueda en LanceDB
        # En producción filtramos por el doc_id del CCyCN para paridad estricta
        qwen_res = prod_tbl.search(qwen_vec).metric("cosine").where("doc_id = '6a9e2ee436300fe5f0afb9d9'").limit(3).to_pandas()
        rwkv_res = lab_tbl.search(rwkv_vec).metric("cosine").limit(3).to_pandas()

        def check_hit(df) -> (bool, bool, str, float, float):
            top1_hit = False
            top3_hit = False
            top1_text = ""
            sim1 = 0.0
            sim2 = 0.0

            if len(df) > 0:
                dist1 = df.iloc[0].get("_distance", 1.0)
                sim1 = 1.0 - dist1
                top1_text = df.iloc[0].get("text", "") or df.iloc[0].get("content", "")
                if f"artículo {target}" in top1_text.lower() or f"art. {target}" in top1_text.lower() or any(k.lower() in top1_text.lower() for k in kws[:2]):
                    top1_hit = True

                if len(df) > 1:
                    sim2 = 1.0 - df.iloc[1].get("_distance", 1.0)

            for rank in range(min(3, len(df))):
                txt = df.iloc[rank].get("text", "") or df.iloc[rank].get("content", "")
                if f"artículo {target}" in txt.lower() or f"art. {target}" in txt.lower() or any(k.lower() in txt.lower() for k in kws[:2]):
                    top3_hit = True
                    break

            return top1_hit, top3_hit, top1_text[:90].replace('\n', ' '), sim1, (sim1 - sim2)

        qwen_t1, qwen_t3, q_snip, q_sim1, q_margin = check_hit(qwen_res)
        rwkv_t1, rwkv_t3, r_snip, r_sim1, r_margin = check_hit(rwkv_res)

        if qwen_t1: qwen_top1 += 1
        if qwen_t3: qwen_top3 += 1
        if rwkv_t1: rwkv_top1 += 1
        if rwkv_t3: rwkv_top3 += 1

        print(f"[{idx:02d}/{len(QUERIES)}] {q_info['tema']} (Art. {target})")
        print(f"   Q: \"{q_text}\"")
        print(f"   🧠 Qwen3:  Top1: {'✔' if qwen_t1 else '❌'} | Top3: {'✔' if qwen_t3 else '❌'} | Sim: {q_sim1:.4f} (Δ: {q_margin:+.4f}) | Res: {q_snip}...")
        print(f"   ⚡ RWKV:   Top1: {'✔' if rwkv_t1 else '❌'} | Top3: {'✔' if rwkv_t3 else '❌'} | Sim: {r_sim1:.4f} (Δ: {r_margin:+.4f}) | Res: {r_snip}...\n")

    total = len(QUERIES)
    print("=" * 75)
    print("📊 RESULTADOS FINALES EN 2.967 CHUNKS DEL CCyCN")
    print("=" * 75)
    print(f"• Qwen3-Embedding-0.6B (Producción):")
    print(f"    - Precisión Top-1 (Rank 1): {qwen_top1}/{total} ({qwen_top1/total*100:.1f}%)")
    print(f"    - Precisión Top-3 (En podio): {qwen_top3}/{total} ({qwen_top3/total*100:.1f}%)")
    print(f"• EmbeddingRWKV-0.4B (Laboratorio):")
    print(f"    - Precisión Top-1 (Rank 1): {rwkv_top1}/{total} ({rwkv_top1/total*100:.1f}%)")
    print(f"    - Precisión Top-3 (En podio): {rwkv_top3}/{total} ({rwkv_top3/total*100:.1f}%)")
    print("=" * 75)


if __name__ == "__main__":
    evaluate()
