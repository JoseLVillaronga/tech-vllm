"""
rag_engine.py - Motor RAG y Búsqueda Vectorial Híbrida con LanceDB
=================================================================
Proporciona almacenamiento vectorial persistente en disco (LanceDB)
e indexación híbrida (Vectores densos Qwen3 de 1024D + Búsqueda de texto completo FTS/BM25).
"""

import os
import sys
import time
import json
import httpx
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LANCEDB_DIR = os.getenv("LANCEDB_PATH", os.path.join(PROJECT_DIR, "data", "lancedb"))
TABLE_NAME = os.getenv("LANCEDB_TABLE_NAME", "teccam_knowledge_base")
EMBEDDINGS_BACKEND_PORT = int(os.getenv("EMBEDDINGS_BACKEND_PORT", "18005"))
MASTER_KEY = os.getenv("API_KEY", "token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939")
TECCAM_PDF_URL_BASE = os.getenv("TECCAM_PDF_URL_BASE", "http://192.168.1.33:5022").rstrip("/")
TECCAM_PDF_API_KEY = os.getenv("TECCAM_PDF_API_KEY", "").strip()

# Asegurar que el directorio de LanceDB existe
os.makedirs(LANCEDB_DIR, exist_ok=True)

_db_instance = None

def get_lancedb():
    """Obtiene la instancia de conexión local de LanceDB."""
    global _db_instance
    if _db_instance is None:
        import lancedb
        _db_instance = lancedb.connect(LANCEDB_DIR)
    return _db_instance

def get_table():
    """Obtiene la tabla de base de conocimiento o None si no existe aún."""
    db = get_lancedb()
    if TABLE_NAME in db.table_names():
        return db.open_table(TABLE_NAME)
    return None

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

def generate_embeddings_batch(texts: List[str], batch_size: int = 32, timeout: float = 30.0) -> List[List[float]]:
    """Genera embeddings en lotes seguros llamando al microservicio vllm-embeddings."""
    if not texts:
        return []
    url = f"http://127.0.0.1:{EMBEDDINGS_BACKEND_PORT}/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {MASTER_KEY}",
        "Content-Type": "application/json"
    }
    
    all_embeddings = []
    with httpx.Client(timeout=timeout) as client:
        for i in range(0, len(texts), batch_size):
            batch_slice = texts[i : i + batch_size]
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
                else:
                    raise RuntimeError(f"Error HTTP {resp.status_code} desde vllm-embeddings: {resp.text}")
            except Exception as e:
                print(f"❌ [RAG Engine] Error generando lote {i}-{i+len(batch_slice)}: {e}", file=sys.stderr)
                raise
                
    return all_embeddings

def get_mongo_db():
    """Obtiene la conexión a MongoDB con autenticación para persistir configuraciones globales de RAG."""
    from pymongo import MongoClient
    user = os.getenv("MONGO_USER", "admin")
    password = os.getenv("MONGO_PASS", "joseMDB365$")
    host = os.getenv("MONGO_HOST", "127.0.0.1")
    db_name = os.getenv("MONGO_DB", "vllm")
    uri = f"mongodb://{user}:{password}@{host}:27017/{db_name}?authSource=admin"
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    return client[db_name]

def get_rag_settings() -> Dict[str, Any]:
    """Obtiene la configuración global de RAG (estado encendido/apagado, dominios activos y modelo cloud para RAG)."""
    try:
        db = get_mongo_db()
        doc = db.rag_settings.find_one({"_id": "global"})
        if doc:
            return {
                "enabled": doc.get("enabled", True),
                "active_topics": doc.get("active_topics", []),
                "cloud_rag_provider_id": doc.get("cloud_rag_provider_id", ""),
                "cloud_rag_provider_name": doc.get("cloud_rag_provider_name", ""),
                "cloud_rag_model_id": doc.get("cloud_rag_model_id", "")
            }
    except Exception:
        pass
    return {
        "enabled": True,
        "active_topics": [],
        "cloud_rag_provider_id": "",
        "cloud_rag_provider_name": "",
        "cloud_rag_model_id": ""
    }

def save_rag_settings(
    active_topics: Optional[List[str]] = None,
    enabled: Optional[bool] = None,
    cloud_rag_provider_id: Optional[str] = None,
    cloud_rag_provider_name: Optional[str] = None,
    cloud_rag_model_id: Optional[str] = None
) -> bool:
    """Guarda la configuración global de dominios/temas activos, estado de activación y modelo cloud para RAG en MongoDB."""
    try:
        db = get_mongo_db()
        update_fields = {"updated_at": time.time()}
        if active_topics is not None:
            update_fields["active_topics"] = active_topics
        if enabled is not None:
            update_fields["enabled"] = bool(enabled)
        if cloud_rag_provider_id is not None:
            update_fields["cloud_rag_provider_id"] = str(cloud_rag_provider_id).strip()
        if cloud_rag_provider_name is not None:
            update_fields["cloud_rag_provider_name"] = str(cloud_rag_provider_name).strip()
        if cloud_rag_model_id is not None:
            update_fields["cloud_rag_model_id"] = str(cloud_rag_model_id).strip()
            
        db.rag_settings.update_one(
            {"_id": "global"},
            {"$set": update_fields},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"⚠️ Error guardando configuración RAG en MongoDB: {e}", file=sys.stderr)
        return False

def search_knowledge_base(
    query: str,
    tema: Optional[Any] = None,
    temas: Optional[List[str]] = None,
    documento_id: Optional[str] = None,
    top_k: int = 5,
    min_score: float = 0.25
) -> List[Dict[str, Any]]:
    """
    Ejecuta una búsqueda híbrida (Vectorial 1024D + FTS BM25) sobre LanceDB.
    
    Args:
        query: Consulta del usuario en lenguaje natural o palabras clave.
        tema: Filtro opcional por tema/dominio (string o lista de strings).
        temas: Filtro opcional por lista de dominios múltiples.
        documento_id: Filtro opcional por ID de libro específico.
        top_k: Cantidad de fragmentos más relevantes a retornar.
        min_score: Umbral mínimo de similitud/relevancia.
        
    Returns:
        Lista de diccionarios con fragmentos, metadatos, citas y puntuación.
    """
    t0 = time.time()
    table = get_table()
    if table is None or len(table) == 0:
        return []

    query_str = query.strip()
    if not query_str:
        return []

    # 1. Generar vector para la consulta del usuario
    query_vector = generate_embedding(query_str)

    # 2. Determinar dominios/temas a filtrar
    topics_to_filter = []
    if temas and isinstance(temas, list):
        topics_to_filter = [t.strip() for t in temas if t and isinstance(t, str) and t.strip()]
    elif tema:
        if isinstance(tema, list):
            topics_to_filter = [t.strip() for t in tema if t and isinstance(t, str) and t.strip()]
        elif isinstance(tema, str) and tema.strip():
            if "," in tema:
                topics_to_filter = [t.strip() for t in tema.split(",") if t.strip()]
            else:
                topics_to_filter = [tema.strip()]
    else:
        # Si no se pasó filtro explícito, aplicar los dominios activos globales si existen
        global_settings = get_rag_settings()
        topics_to_filter = global_settings.get("active_topics", [])

    # 3. Construir filtro SQL / pre-filter si aplica
    filter_clauses = []
    if topics_to_filter:
        clean_temas = [f"'{t.replace('\'', '\'\'')}'" for t in topics_to_filter if t]
        if len(clean_temas) == 1:
            filter_clauses.append(f"doc_topic = {clean_temas[0]}")
        elif len(clean_temas) > 1:
            filter_clauses.append(f"doc_topic IN ({', '.join(clean_temas)})")

    if documento_id and documento_id.strip():
        clean_doc_id = documento_id.strip().replace("'", "''")
        filter_clauses.append(f"doc_id = '{clean_doc_id}'")
        
    filter_expr = " AND ".join(filter_clauses) if filter_clauses else None

    all_candidates = {}
    
    # A) Búsqueda vectorial semántica (1024D)
    try:
        vec_builder = table.search(query_vector, query_type="vector")
        if filter_expr:
            vec_builder = vec_builder.where(filter_expr)
        vec_results = vec_builder.limit(top_k * 5).to_list()
        
        for item in vec_results:
            d_id = item.get("id")
            dist = item.get("_distance", 1.0)
            similarity = max(0.0, 1.0 - (dist / 2.0))
            all_candidates[d_id] = {
                "item": item,
                "vec_sim": similarity,
                "fts_score": 0.0,
                "dist": dist
            }
    except Exception as ve:
        print(f"⚠️ [RAG Engine] Error en búsqueda vectorial: {ve}", file=sys.stderr)

    # B) Búsqueda de texto completo (BM25 / FTS)
    try:
        fts_builder = table.search(query_str, query_type="fts")
        if filter_expr:
            fts_builder = fts_builder.where(filter_expr)
        fts_results = fts_builder.limit(top_k * 5).to_list()
        
        max_fts = max([r.get("_score", 0.0) for r in fts_results]) if fts_results else 1.0
        if max_fts <= 0:
            max_fts = 1.0
            
        for item in fts_results:
            d_id = item.get("id")
            raw_score = item.get("_score", 0.0)
            norm_fts = raw_score / max_fts
            
            if d_id in all_candidates:
                all_candidates[d_id]["fts_score"] = norm_fts
            else:
                all_candidates[d_id] = {
                    "item": item,
                    "vec_sim": 0.65, # Baseline de similitud semántica para matches léxicos
                    "fts_score": norm_fts,
                    "dist": 0.70
                }
    except Exception as fe:
        pass

    results = []
    for d_id, data in all_candidates.items():
        item = data["item"]
        v_sim = data["vec_sim"]
        f_sim = data["fts_score"]
        
        # Fusión híbrida ponderada
        if f_sim > 0:
            final_sim = (v_sim * 0.45) + (f_sim * 0.55)
        else:
            final_sim = v_sim
            
        if final_sim >= min_score or len(results) < top_k:
            results.append({
                "id": item.get("id"),
                "doc_id": item.get("doc_id"),
                "doc_title": item.get("doc_title"),
                "doc_author": item.get("doc_author"),
                "doc_topic": item.get("doc_topic"),
                "section_path": item.get("section_path"),
                "chunk_index": item.get("chunk_index"),
                "content": item.get("content"),
                "enriched_text": item.get("text"),
                "similarity": round(final_sim, 4),
                "distance": round(data["dist"], 4)
            })

    # Ordenar por score híbrido y limitar a top_k
    final_results = sorted(results, key=lambda x: x["similarity"], reverse=True)[:top_k]
    dur_ms = (time.time() - t0) * 1000
    print(f"🔍 [RAG Search] Consulta: '{query_str[:40]}...' | {len(final_results)} resultados en {dur_ms:.2f} ms")
    return final_results

def format_rag_context_for_llm(results: List[Dict[str, Any]]) -> str:
    """Formatea los resultados de búsqueda en un bloque de contexto claro y estructurado con citas para Gemma."""
    if not results:
        return "No se encontraron fragmentos relevantes en la base de conocimiento de Teccam."
        
    snippets = []
    for idx, item in enumerate(results, 1):
        doc_title = item.get("doc_title", "Documento sin título")
        doc_topic = item.get("doc_topic", "General")
        section = item.get("section_path", "Sección Principal")
        author = item.get("doc_author", "Desconocido")
        content = item.get("content", "").strip()
        sim_pct = int(item.get("similarity", 0) * 100)
        
        snippets.append(
            f"--- FUENTE [{idx}]: \"{doc_title}\" (Tema: {doc_topic} | Sección: {section} | Autor: {author} | Coincidencia: {sim_pct}%) ---\n"
            f"{content}"
        )
        
    return "\n\n".join(snippets)

def get_rag_stats() -> Dict[str, Any]:
    """Obtiene métricas y estadísticas globales de la base de conocimiento en LanceDB."""
    table = get_table()
    if table is None:
        return {
            "is_initialized": False,
            "total_chunks": 0,
            "total_documents": 0,
            "documents": [],
            "topics": [],
            "lancedb_path": LANCEDB_DIR,
            "table_name": TABLE_NAME
        }
        
    try:
        total_chunks = len(table)
        df = table.to_arrow()
        
        doc_ids = df["doc_id"].to_pylist() if "doc_id" in df.schema.names else []
        doc_titles = df["doc_title"].to_pylist() if "doc_title" in df.schema.names else []
        doc_topics = df["doc_topic"].to_pylist() if "doc_topic" in df.schema.names else []
        
        docs_map = {}
        for d_id, d_title, d_topic in zip(doc_ids, doc_titles, doc_topics):
            if d_id not in docs_map:
                docs_map[d_id] = {
                    "id": d_id,
                    "title": d_title,
                    "topic": d_topic,
                    "chunks_count": 0
                }
            docs_map[d_id]["chunks_count"] += 1
            
        topics_count = {}
        for t in doc_topics:
            if t:
                topics_count[t] = topics_count.get(t, 0) + 1
                
        topics_list = [{"name": k, "chunks_count": v} for k, v in topics_count.items()]
        
        rag_sett = get_rag_settings()
        return {
            "is_initialized": True,
            "enabled": rag_sett.get("enabled", True),
            "total_chunks": total_chunks,
            "total_documents": len(docs_map),
            "documents": list(docs_map.values()),
            "topics": topics_list,
            "active_topics": rag_sett.get("active_topics", []),
            "lancedb_path": LANCEDB_DIR,
            "table_name": TABLE_NAME
        }
    except Exception as e:
        print(f"⚠️ [RAG Engine] Error obteniendo estadísticas de LanceDB: {e}", file=sys.stderr)
        return {
            "is_initialized": True,
            "total_chunks": len(table) if table else 0,
            "total_documents": 0,
            "documents": [],
            "topics": [],
            "error": str(e)
        }

def fetch_teccam_document_raw(doc_id: str) -> Optional[Dict[str, Any]]:
    """Consulta la API de Teccam PDF (:5022) para obtener el Markdown íntegro original desde MongoDB."""
    if not TECCAM_PDF_URL_BASE:
        return None
    url = f"{TECCAM_PDF_URL_BASE}/api/v1/rag/documentos/{doc_id}"
    headers = {}
    if TECCAM_PDF_API_KEY:
        headers["Authorization"] = f"Bearer {TECCAM_PDF_API_KEY}"
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"⚠️ [RAG Engine] Teccam PDF respondió HTTP {resp.status_code} para {doc_id}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ [RAG Engine] Error al consultar API de Teccam PDF ({url}): {e}", file=sys.stderr)
    return None

def get_document_full_content(
    doc_id: str,
    parte: int = 1,
    chunk_threshold: int = 275
) -> Dict[str, Any]:
    """
    Obtiene el contenido completo o paginado de un documento para síntesis exhaustiva por el LLM.
    
    Estrategia Híbrida:
    - Si total_chunks <= 275: Recupera el Markdown original 1:1 desde la API de Teccam PDF (:5022).
      Fallback: Si la API de Teccam no responde, concatena los fragmentos desde LanceDB.
    - Si total_chunks > 275: Divide el documento en partes de hasta 275 fragmentos desde LanceDB.
    """
    clean_doc_id = doc_id.strip()
    table = get_table()
    if table is None or len(table) == 0:
        return {
            "success": False,
            "error": "Base vectorial LanceDB no inicializada o vacía.",
            "doc_id": clean_doc_id
        }

    # 1. Consultar todos los chunks de este documento en LanceDB
    clean_sql_id = clean_doc_id.replace("'", "''")
    results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()
    
    if len(results) == 0:
        return {
            "success": False,
            "error": f"No se encontró ningún documento con ID '{clean_doc_id}' en la base de conocimiento.",
            "doc_id": clean_doc_id
        }
        
    doc_title = results["doc_title"][0].as_py() if "doc_title" in results.schema.names else "Documento"
    doc_topic = results["doc_topic"][0].as_py() if "doc_topic" in results.schema.names else "General"
    doc_author = results["doc_author"][0].as_py() if "doc_author" in results.schema.names else "Desconocido"
    total_chunks = len(results)
    
    # 2. ESCENARIO A: Documentos Cortos/Medianos (<= 275 chunks) -> Fidelidad Total desde Teccam PDF
    if total_chunks <= chunk_threshold:
        raw_detail = fetch_teccam_document_raw(clean_doc_id)
        if raw_detail and raw_detail.get("texto", "").strip():
            raw_text = raw_detail.get("texto", "").strip()
            header = (
                f"# {doc_title}\n"
                f"**Tema / Dominio:** {doc_topic} | **Autor:** {doc_author} | **Total Fragmentos:** {total_chunks}\n"
                f"**Modo de Recuperación:** Documento Íntegro Oficial (Fidelidad 100% desde Teccam PDF)\n\n"
                f"---\n\n"
            )
            return {
                "success": True,
                "doc_id": clean_doc_id,
                "titulo": doc_title,
                "tema": doc_topic,
                "autor": doc_author,
                "total_chunks": total_chunks,
                "modo": "completo_directo",
                "parte_actual": 1,
                "total_partes": 1,
                "content": header + raw_text
            }
            
        # Fallback a concatenación desde LanceDB si la API de Teccam PDF no estaba disponible
        print(f"ℹ️ [RAG Engine] Fallback a concatenación de LanceDB para '{doc_title}' ({clean_doc_id})", file=sys.stderr)
        
    # 3. ESCENARIO B: Libros/Códigos Masivos (> 275 chunks) o Fallback LanceDB
    ids = results["id"].to_pylist() if "id" in results.schema.names else []
    sections = results["section_path"].to_pylist() if "section_path" in results.schema.names else []
    contents = results["content"].to_pylist() if "content" in results.schema.names else []
    
    # Ordenar chunks por ID secuencial (doc_id_0000, doc_id_0001, etc.)
    sorted_items = sorted(zip(ids, sections, contents), key=lambda x: x[0])
    
    total_partes = max(1, (total_chunks + chunk_threshold - 1) // chunk_threshold)
    parte = max(1, min(parte, total_partes))
    
    start_idx = (parte - 1) * chunk_threshold
    end_idx = min(start_idx + chunk_threshold, total_chunks)
    slice_items = sorted_items[start_idx:end_idx]
    
    body_parts = []
    current_sec = None
    for _, sec, cont in slice_items:
        if sec != current_sec:
            current_sec = sec
            body_parts.append(f"\n\n### {sec}\n")
        body_parts.append(cont)
        
    slice_text = "\n\n".join(body_parts).strip()
    
    if total_chunks <= chunk_threshold:
        modo_str = "completo_lancedb"
        header = (
            f"# {doc_title}\n"
            f"**Tema / Dominio:** {doc_topic} | **Autor:** {doc_author} | **Total Fragmentos:** {total_chunks}\n"
            f"**Modo de Recuperación:** Documento Completo Reconstruido desde LanceDB\n\n"
            f"---\n\n"
        )
    else:
        modo_str = "paginado"
        next_hint = f" (Para leer la siguiente parte use parte={parte+1})" if parte < total_partes else " (Fin del documento)"
        header = (
            f"# {doc_title} (Parte {parte} de {total_partes})\n"
            f"**Tema / Dominio:** {doc_topic} | **Autor:** {doc_author} | **Fragmentos:** {start_idx + 1} al {end_idx} (de {total_chunks})\n"
            f"**Aviso de Paginación:** Documento extenso dividido en bloques de {chunk_threshold} fragmentos.{next_hint}\n\n"
            f"---\n\n"
        )
        
    return {
        "success": True,
        "doc_id": clean_doc_id,
        "titulo": doc_title,
        "tema": doc_topic,
        "autor": doc_author,
        "total_chunks": total_chunks,
        "modo": modo_str,
        "parte_actual": parte,
        "total_partes": total_partes,
        "chunks_en_esta_parte": len(slice_items),
        "content": header + slice_text
    }
