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
from config import API_KEY as MASTER_KEY, get_mongo_uri, MONGO_DB
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

def get_mongo_db():
    """Obtiene la conexión a MongoDB con autenticación para persistir configuraciones globales de RAG."""
    from pymongo import MongoClient
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=2000)
    return client[MONGO_DB]

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
                "chunk_tokens": item.get("chunk_tokens"),
                "total_chunks": item.get("total_chunks"),
                "total_doc_tokens": item.get("total_doc_tokens"),
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
    """Formatea los resultados de búsqueda en un bloque de contexto claro y estructurado con citas y doc_id para el LLM."""
    if not results:
        return "No se encontraron fragmentos relevantes en la base de conocimiento de Teccam."
        
    snippets = []
    for idx, item in enumerate(results, 1):
        doc_title = item.get("doc_title", "Documento sin título")
        doc_id = item.get("doc_id", "")
        doc_topic = item.get("doc_topic", "General")
        section = item.get("section_path", "Sección Principal")
        author = item.get("doc_author", "Desconocido")
        content = item.get("content", "").strip()
        sim_pct = int(item.get("similarity", 0) * 100)
        c_tokens = item.get("chunk_tokens")
        tot_tokens = item.get("total_doc_tokens") or 0
        tokens_tag = f" | Tokens: ~{c_tokens}" if c_tokens else ""
        
        # Si el documento supera los 30.000 tokens o 100 fragmentos, incluir guía de GPS Documental y lectura por sección
        if tot_tokens > 30000 or item.get("total_chunks", 0) > 100:
            clean_sec_hint = section.split(">")[-1].strip() if ">" in section else section
            action_hint = (
                f"💡 [Acción Disponible (Obra Extensa ~{tot_tokens:,} tokens)]:\n"
                f"   - Para explorar el índice/GPS de capítulos usa: obtener_estructura_documento(doc_id=\"{doc_id}\")\n"
                f"   - Para leer una sección o libro específico usa: leer_documento_completo(doc_id=\"{doc_id}\", seccion=\"{clean_sec_hint}\")"
            )
        else:
            action_hint = f"💡 [Acción Disponible: Para leer este documento completo o hacer una síntesis integral usa: leer_documento_completo(doc_id=\"{doc_id}\")]"
        
        snippets.append(
            f"--- FUENTE [{idx}]: \"{doc_title}\" [doc_id: {doc_id}] (Tema: {doc_topic} | Sección: {section} | Autor: {author}{tokens_tag} | Coincidencia: {sim_pct}%) ---\n"
            f"{action_hint}\n"
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

import unicodedata

def normalize_text(text: str) -> str:
    """Elimina acentos, diacríticos y normaliza a minúsculas para comparaciones tolerantes."""
    if not text:
        return ""
    text = str(text).lower().strip()
    nfkd = unicodedata.normalize('NFKD', text)
    cleaned = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ' '.join(cleaned.split())

def find_documents_by_fuzzy_title(query: str) -> List[Dict[str, Any]]:
    """
    Busca documentos en LanceDB que coincidan con la consulta por título, palabras clave o substring (estilo SQL LIKE %...%).
    Tolera diferencias de acentos, mayúsculas, signos de puntuación y orden de palabras.
    """
    table = get_table()
    if table is None or len(table) == 0:
        return []
        
    df = table.to_arrow()
    if "doc_title" not in df.schema.names or "doc_id" not in df.schema.names:
        return []
        
    titles = df["doc_title"].to_pylist()
    ids = df["doc_id"].to_pylist()
    topics = df["doc_topic"].to_pylist() if "doc_topic" in df.schema.names else ["General"] * len(ids)
    authors = df["doc_author"].to_pylist() if "doc_author" in df.schema.names else ["Desconocido"] * len(ids)
    
    unique_docs = {}
    for d_id, t, top, aut in zip(ids, titles, topics, authors):
        if d_id not in unique_docs:
            unique_docs[d_id] = {
                "doc_id": d_id,
                "title": t,
                "topic": top,
                "author": aut,
                "chunks_count": 0
            }
        unique_docs[d_id]["chunks_count"] += 1
        
    q_norm = normalize_text(query)
    q_words = set(w for w in q_norm.split() if len(w) > 2)
    
    candidates = []
    for d_id, doc in unique_docs.items():
        t_norm = normalize_text(doc["title"])
        t_words = set(w for w in t_norm.split() if len(w) > 2)
        
        score = 0.0
        # 1. Coincidencia exacta normalizada
        if q_norm == t_norm:
            score = 1.0
        # 2. Substring (LIKE %...%)
        elif q_norm in t_norm or t_norm in q_norm:
            score = 0.90
        # 3. Coincidencia por conjunto de palabras clave
        else:
            common = q_words.intersection(t_words)
            if common and (len(common) >= min(len(q_words), 2) or len(common) == len(q_words)):
                score = len(common) / max(len(q_words), len(t_words))
                
        if score >= 0.20:
            candidates.append({
                **doc,
                "score": round(score, 2)
            })
            
    return sorted(candidates, key=lambda x: x["score"], reverse=True)

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

def get_document_structure(doc_id: str) -> Dict[str, Any]:
    """
    Construye el 'GPS Documental' (Árbol y Mapa de Estructura de Secciones) de una obra desde LanceDB.
    
    Permite al LLM y al usuario explorar la jerarquía, el volumen de tokens por sección y los rangos de fragmentos
    antes de solicitar la lectura de capítulos, títulos o partes específicas.
    """
    clean_doc_id = doc_id.strip()
    table = get_table()
    if table is None or len(table) == 0:
        return {
            "success": False,
            "error": "Base vectorial LanceDB no inicializada o vacía.",
            "doc_id": clean_doc_id
        }

    # 1. Consultar todos los chunks en LanceDB
    clean_sql_id = clean_doc_id.replace("'", "''")
    results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()

    # 2. Búsqueda difusa si no se encontró por ID
    candidates = []
    if len(results) == 0:
        candidates = find_documents_by_fuzzy_title(clean_doc_id)
        if candidates:
            best_match = candidates[0]
            clean_doc_id = best_match["doc_id"]
            clean_sql_id = clean_doc_id.replace("'", "''")
            results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()

    if len(results) == 0:
        stats = get_rag_stats()
        avail = [f"- '{d['title']}' [doc_id: {d['id']}]" for d in stats.get("documents", [])[:10]]
        return {
            "success": False,
            "error": f"No se encontró ningún documento con ID o título que coincida con '{clean_doc_id}'.\n\nDocumentos disponibles:\n" + "\n".join(avail),
            "doc_id": clean_doc_id
        }

    actual_doc_id = results["doc_id"][0].as_py() if "doc_id" in results.schema.names else clean_doc_id
    doc_title = results["doc_title"][0].as_py() if "doc_title" in results.schema.names else "Documento"
    doc_topic = results["doc_topic"][0].as_py() if "doc_topic" in results.schema.names else "General"
    doc_author = results["doc_author"][0].as_py() if "doc_author" in results.schema.names else "Desconocido"
    total_chunks = len(results)

    ids = results["id"].to_pylist() if "id" in results.schema.names else []
    sections = results["section_path"].to_pylist() if "section_path" in results.schema.names else []
    contents = results["content"].to_pylist() if "content" in results.schema.names else []
    chunk_tokens = results["chunk_tokens"].to_pylist() if "chunk_tokens" in results.schema.names else [len(c)//4 for c in contents]

    raw_doc_tokens = results["total_doc_tokens"][0].as_py() if "total_doc_tokens" in results.schema.names else None
    if raw_doc_tokens and raw_doc_tokens > 0:
        total_doc_tokens = int(raw_doc_tokens)
    else:
        total_doc_tokens = sum(tok if (tok and tok > 0) else max(1, len(c)//4) for tok, c in zip(chunk_tokens, contents))

    # 3. Analizar y agrupar secciones secuencialmente
    sorted_items = sorted(zip(ids, sections, contents, chunk_tokens), key=lambda x: x[0])
    
    sections_list = []
    current_sec_name = None
    current_sec_tokens = 0
    current_sec_chunks = 0
    start_chunk_idx = 1
    
    for idx, (ch_id, sec_path, cont, tok_cnt) in enumerate(sorted_items, 1):
        t_c = tok_cnt if (tok_cnt and tok_cnt > 0) else max(1, len(cont) // 4)
        sec_name = sec_path.strip() if sec_path and sec_path.strip() else "Contenido Principal"
        
        if current_sec_name is None:
            current_sec_name = sec_name
            current_sec_tokens = t_c
            current_sec_chunks = 1
            start_chunk_idx = idx
        elif sec_name == current_sec_name:
            current_sec_tokens += t_c
            current_sec_chunks += 1
        else:
            sections_list.append({
                "index": len(sections_list) + 1,
                "section": current_sec_name,
                "chunk_start": start_chunk_idx,
                "chunk_end": idx - 1,
                "chunks_count": current_sec_chunks,
                "estimated_tokens": current_sec_tokens
            })
            current_sec_name = sec_name
            current_sec_tokens = t_c
            current_sec_chunks = 1
            start_chunk_idx = idx
            
    if current_sec_name is not None:
        sections_list.append({
            "index": len(sections_list) + 1,
            "section": current_sec_name,
            "chunk_start": start_chunk_idx,
            "chunk_end": len(sorted_items),
            "chunks_count": current_sec_chunks,
            "estimated_tokens": current_sec_tokens
        })

    # 4. Formatear la tabla Markdown del GPS Documental
    md_rows = []
    for s in sections_list:
        sec_display = s["section"]
        if len(sec_display) > 80:
            sec_display = sec_display[:77] + "..."
        clean_param = s["section"].split(">")[-1].strip().replace('"', '')
        if len(clean_param) < 4 and ">" in s["section"]:
            clean_param = s["section"].split(">")[-2].strip().replace('"', '')
        md_rows.append(
            f"| `{s['index']:02d}` | **{sec_display}** | {s['chunks_count']} | ~{s['estimated_tokens']:,} | `leer_documento_completo(doc_id=\"{actual_doc_id}\", seccion=\"{clean_param}\")` |"
        )

    table_header = (
        "| # | Sección / Capítulo / Módulo | Chunks | Tokens | Invocación Focalizada Sugerida |\n"
        "| :---: | :--- | :---: | :---: | :--- |\n"
    )

    alt_notice = ""
    if candidates and len(candidates) > 1:
        other_matches = [f"'{c['title']}' (doc_id: {c['doc_id']})" for c in candidates[1:4]]
        alt_notice = f"💡 *Nota de Búsqueda:* Se seleccionó '{doc_title}'. Otras coincidencias: {', '.join(other_matches)}\n\n"

    content_md = (
        f"# 🗺️ GPS Documental: Mapa de Estructura de Secciones\n"
        f"**Documento:** \"{doc_title}\" [doc_id: `{actual_doc_id}`]\n"
        f"**Tema:** {doc_topic} | **Autor:** {doc_author} | **Total Obra:** ~{total_doc_tokens:,} tokens ({total_chunks} fragmentos, {len(sections_list)} secciones detectadas)\n\n"
        f"{alt_notice}"
        f"A continuación se presenta el árbol estructural de la obra para orientar la lectura y análisis focalizado:\n\n"
        f"{table_header}" + "\n".join(md_rows) + "\n\n"
        f"---\n"
        f"💡 **Guía de Navegación para el LLM y Usuario:**\n"
        f"- Para leer una sección específica sin desbordar el contexto, ejecuta: `leer_documento_completo(doc_id=\"{actual_doc_id}\", seccion=\"<nombre_de_seccion>\")`.\n"
        f"- Para paginación secuencial completa, ejecuta: `leer_documento_completo(doc_id=\"{actual_doc_id}\", parte=1)`."
    )

    return {
        "success": True,
        "doc_id": actual_doc_id,
        "titulo": doc_title,
        "tema": doc_topic,
        "autor": doc_author,
        "total_chunks": total_chunks,
        "total_doc_tokens": total_doc_tokens,
        "sections_count": len(sections_list),
        "sections": sections_list,
        "content": content_md
    }

def _partition_chunks_dynamically(
    sorted_items: List[tuple],
    target_tokens: int,
    tolerance_pct: float = 0.08
) -> List[tuple]:
    """
    Divide una secuencia de chunks en partes dinámicas buscando límites limpios de sección.
    
    Aplica una ventana de tolerancia [target * (1 - tolerance), target * (1 + tolerance)] (ej: ±8%)
    para cortar preferentemente en cambios de sección (`section_path`) en lugar de partir artículos a ciegas.
    """
    min_tokens = int(target_tokens * (1.0 - tolerance_pct))
    max_tokens = int(target_tokens * (1.0 + tolerance_pct))

    partes = []
    current_part = []
    current_tokens = 0

    for i, item in enumerate(sorted_items):
        ch_id, sec, cont, tok_cnt = item
        t_c = tok_cnt if (tok_cnt and tok_cnt > 0) else max(1, len(cont) // 4)

        next_sec = sorted_items[i + 1][1] if (i + 1 < len(sorted_items)) else None
        is_section_boundary = (next_sec is not None and next_sec != sec)

        current_part.append(item)
        current_tokens += t_c

        if is_section_boundary and current_tokens >= min_tokens:
            partes.append((current_part, current_tokens))
            current_part = []
            current_tokens = 0
        elif current_tokens >= max_tokens:
            partes.append((current_part, current_tokens))
            current_part = []
            current_tokens = 0

    if current_part:
        partes.append((current_part, current_tokens))

    return partes

def get_document_full_content(
    doc_id: str,
    parte: int = 1,
    token_threshold: int = 60000,
    chunk_threshold: Optional[int] = None,
    seccion: Optional[str] = None
) -> Dict[str, Any]:
    """
    Obtiene el contenido completo, por sección temática o paginado con tolerancia dinámica (±5%-8%) de un documento.
    
    Características del RAG Jerárquico:
    - Búsqueda tolerante por ID o título difuso.
    - Soporte para extracción focalizada de una sección (`seccion='Libro Primero'` o `seccion='Objetivo'`).
    - Particionado inteligente con alineación a límites naturales de sección dentro del rango de tolerancia (±5%-8%).
    """
    clean_doc_id = doc_id.strip()
    table = get_table()
    if table is None or len(table) == 0:
        return {
            "success": False,
            "error": "Base vectorial LanceDB no inicializada o vacía.",
            "doc_id": clean_doc_id
        }

    # Compatibilidad hacia atrás si se pasa chunk_threshold
    effective_token_threshold = token_threshold
    if chunk_threshold is not None and chunk_threshold > 0:
        effective_token_threshold = chunk_threshold * 220

    # 1. Consultar todos los chunks de este documento en LanceDB por doc_id exacto
    clean_sql_id = clean_doc_id.replace("'", "''")
    results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()
    
    # 2. Si no se encontró por ID exacto, buscar con el motor difuso tolerante a acentos y substrings
    candidates = []
    if len(results) == 0:
        candidates = find_documents_by_fuzzy_title(clean_doc_id)
        if candidates:
            best_match = candidates[0]
            clean_doc_id = best_match["doc_id"]
            clean_sql_id = clean_doc_id.replace("'", "''")
            results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()
    
    if len(results) == 0:
        stats = get_rag_stats()
        avail = [f"- '{d['title']}' [doc_id: {d['id']}]" for d in stats.get("documents", [])[:10]]
        return {
            "success": False,
            "error": f"No se encontró ningún documento con ID o título que coincida con '{clean_doc_id}'.\n\nDocumentos disponibles en la biblioteca:\n" + "\n".join(avail),
            "doc_id": clean_doc_id
        }
        
    actual_doc_id = results["doc_id"][0].as_py() if "doc_id" in results.schema.names else clean_doc_id
    doc_title = results["doc_title"][0].as_py() if "doc_title" in results.schema.names else "Documento"
    doc_topic = results["doc_topic"][0].as_py() if "doc_topic" in results.schema.names else "General"
    doc_author = results["doc_author"][0].as_py() if "doc_author" in results.schema.names else "Desconocido"
    total_chunks = len(results)

    ids = results["id"].to_pylist() if "id" in results.schema.names else []
    sections = results["section_path"].to_pylist() if "section_path" in results.schema.names else []
    contents = results["content"].to_pylist() if "content" in results.schema.names else []
    chunk_tokens = results["chunk_tokens"].to_pylist() if "chunk_tokens" in results.schema.names else [len(c)//4 for c in contents]
    
    raw_doc_tokens = results["total_doc_tokens"][0].as_py() if "total_doc_tokens" in results.schema.names else None
    if raw_doc_tokens and raw_doc_tokens > 0:
        total_doc_tokens = int(raw_doc_tokens)
    else:
        total_doc_tokens = sum(tok if (tok and tok > 0) else max(1, len(c)//4) for tok, c in zip(chunk_tokens, contents))

    sorted_items = sorted(zip(ids, sections, contents, chunk_tokens), key=lambda x: x[0])

    alt_notice = ""
    if candidates and len(candidates) > 1:
        other_matches = [f"'{c['title']}' (doc_id: {c['doc_id']})" for c in candidates[1:4]]
        alt_notice = f"💡 *Nota de Búsqueda:* Se seleccionó '{doc_title}'. Otras coincidencias posibles: {', '.join(other_matches)}\n\n"

    # =========================================================================
    # CASO 1: BÚSQUEDA FOCALIZADA POR SECCIÓN O CAPÍTULO
    # =========================================================================
    if seccion and seccion.strip():
        req_sec_norm = normalize_text(seccion)
        matched_items = []
        for ch_id, sec, cont, tok_cnt in sorted_items:
            s_norm = normalize_text(sec)
            if req_sec_norm in s_norm or s_norm in req_sec_norm:
                matched_items.append((ch_id, sec, cont, tok_cnt))
                
        if not matched_items:
            unique_secs = []
            for _, s, _, _ in sorted_items:
                if s and s not in unique_secs:
                    unique_secs.append(s)
            avail_secs = "\n".join([f"- {s}" for s in unique_secs[:15]])
            return {
                "success": False,
                "error": f"No se encontró la sección '{seccion}' en el documento '{doc_title}'.\n\nSecciones principales disponibles:\n{avail_secs}\n\n💡 Tip: Usa obtener_estructura_documento(doc_id=\"{actual_doc_id}\") para ver el índice completo.",
                "doc_id": actual_doc_id
            }

        sec_tokens = sum(t_c if (t_c and t_c > 0) else max(1, len(c) // 4) for _, _, c, t_c in matched_items)
        sec_name = matched_items[0][1]

        if sec_tokens <= effective_token_threshold:
            body_parts = []
            current_sec = None
            for _, s, cont, _ in matched_items:
                if s != current_sec:
                    current_sec = s
                    body_parts.append(f"\n\n### {s}\n")
                body_parts.append(cont)
            slice_text = "\n\n".join(body_parts).strip()
            header = (
                f"# {doc_title} — Sección: \"{sec_name}\"\n"
                f"**ID:** {actual_doc_id} | **Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens Sección:** ~{sec_tokens:,} ({len(matched_items)} fragmentos) | **Total Obra:** ~{total_doc_tokens:,} tokens\n"
                f"**Modo de Recuperación:** Sección Focalizada Verificada desde LanceDB\n\n"
                f"{alt_notice}"
                f"---\n\n"
            )
            return {
                "success": True,
                "doc_id": actual_doc_id,
                "titulo": doc_title,
                "tema": doc_topic,
                "autor": doc_author,
                "seccion_solicitada": seccion,
                "seccion_nombre": sec_name,
                "total_chunks": total_chunks,
                "total_doc_tokens": total_doc_tokens,
                "tokens_en_esta_parte": sec_tokens,
                "chunks_en_esta_parte": len(matched_items),
                "modo": "seccion_focalizada",
                "parte_actual": 1,
                "total_partes": 1,
                "content": header + slice_text
            }
        else:
            partes_chunks = _partition_chunks_dynamically(matched_items, effective_token_threshold)
            total_partes = max(1, len(partes_chunks))
            parte = max(1, min(parte, total_partes))
            selected_slice, part_tokens = partes_chunks[parte - 1]
            body_parts = []
            current_sec = None
            for _, s, cont, _ in selected_slice:
                if s != current_sec:
                    current_sec = s
                    body_parts.append(f"\n\n### {s}\n")
                body_parts.append(cont)
            slice_text = "\n\n".join(body_parts).strip()
            next_hint = f" (Para leer la siguiente parte de esta sección use parte={parte+1})" if parte < total_partes else " (Fin de la sección)"
            header = (
                f"# {doc_title} — Sección: \"{sec_name}\" (Parte {parte} de {total_partes})\n"
                f"**ID:** {actual_doc_id} | **Tokens en esta parte:** ~{part_tokens:,} ({len(selected_slice)} fragmentos) | **Total Sección:** ~{sec_tokens:,} tokens\n"
                f"**Aviso:** Sección extensa dividida con límites limpios de tolerancia.{next_hint}\n\n"
                f"---\n\n"
            )
            return {
                "success": True,
                "doc_id": actual_doc_id,
                "titulo": doc_title,
                "tema": doc_topic,
                "autor": doc_author,
                "seccion_solicitada": seccion,
                "seccion_nombre": sec_name,
                "total_chunks": total_chunks,
                "total_doc_tokens": total_doc_tokens,
                "tokens_en_esta_parte": part_tokens,
                "chunks_en_esta_parte": len(selected_slice),
                "modo": "seccion_paginada",
                "parte_actual": parte,
                "total_partes": total_partes,
                "content": header + slice_text
            }

    # =========================================================================
    # CASO 2: DOCUMENTO COMPLETO (< 60.000 tokens) -> 1:1 TECCAM PDF O LANCEDB
    # =========================================================================
    if total_doc_tokens <= effective_token_threshold:
        raw_detail = fetch_teccam_document_raw(actual_doc_id)
        if raw_detail and raw_detail.get("texto", "").strip():
            raw_text = raw_detail.get("texto", "").strip()
            header = (
                f"# {doc_title}\n"
                f"**ID:** {actual_doc_id} | **Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens:** ~{total_doc_tokens:,} ({total_chunks} fragmentos)\n"
                f"**Modo de Recuperación:** Documento Íntegro Oficial (Fidelidad 100% desde Teccam PDF)\n\n"
                f"{alt_notice}"
                f"---\n\n"
            )
            return {
                "success": True,
                "doc_id": actual_doc_id,
                "titulo": doc_title,
                "tema": doc_topic,
                "autor": doc_author,
                "total_chunks": total_chunks,
                "total_doc_tokens": total_doc_tokens,
                "tokens_en_esta_parte": total_doc_tokens,
                "modo": "completo_directo",
                "parte_actual": 1,
                "total_partes": 1,
                "content": header + raw_text
            }

    # =========================================================================
    # CASO 3: OBRAS MASIVAS (> 60.000 tokens) CON TOLERANCIA DINÁMICA (±5%-8%)
    # =========================================================================
    partes_chunks = _partition_chunks_dynamically(sorted_items, effective_token_threshold)
    total_partes = max(1, len(partes_chunks))
    parte = max(1, min(parte, total_partes))
    selected_slice, part_tokens = partes_chunks[parte - 1]

    body_parts = []
    current_sec = None
    for _, sec, cont, _ in selected_slice:
        if sec != current_sec:
            current_sec = sec
            body_parts.append(f"\n\n### {sec}\n")
        body_parts.append(cont)
    slice_text = "\n\n".join(body_parts).strip()

    if total_partes == 1:
        modo_str = "completo_lancedb"
        header = (
            f"# {doc_title}\n"
            f"**Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens:** ~{part_tokens:,} ({len(selected_slice)} fragmentos)\n"
            f"**Modo de Recuperación:** Documento Completo Reconstruido desde LanceDB\n\n"
            f"---\n\n"
        )
    else:
        modo_str = "paginado_jerarquico"
        next_hint = f" (Para leer la siguiente parte use parte={parte+1})" if parte < total_partes else " (Fin del documento)"
        header = (
            f"# {doc_title} (Parte {parte} de {total_partes})\n"
            f"**Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens en esta parte:** ~{part_tokens:,} ({len(selected_slice)} fragmentos) | **Total Obra:** ~{total_doc_tokens:,} tokens ({total_chunks} fragmentos)\n"
            f"**Aviso de Paginación Jerárquica:** Cortes alineados a límites naturales de capítulos con tolerancia dinámica (±5%-8%).{next_hint}\n"
            f"💡 **Tip:** Puedes consultar el mapa general con `obtener_estructura_documento(doc_id=\"{actual_doc_id}\")` o solicitar una sección directa.\n\n"
            f"---\n\n"
        )

    return {
        "success": True,
        "doc_id": actual_doc_id,
        "titulo": doc_title,
        "tema": doc_topic,
        "autor": doc_author,
        "total_chunks": total_chunks,
        "total_doc_tokens": total_doc_tokens,
        "tokens_en_esta_parte": part_tokens,
        "chunks_en_esta_parte": len(selected_slice),
        "modo": modo_str,
        "parte_actual": parte,
        "total_partes": total_partes,
        "content": header + slice_text
    }
