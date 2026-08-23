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

def search_knowledge_base(
    query: str,
    tema: Optional[str] = None,
    documento_id: Optional[str] = None,
    top_k: int = 5,
    min_score: float = 0.25
) -> List[Dict[str, Any]]:
    """
    Ejecuta una búsqueda sobre LanceDB.
    
    Args:
        query: Consulta del usuario en lenguaje natural o palabras clave.
        tema: Filtro opcional por tema/dominio (ej: 'Derecho Argentino', 'Procedimientos Teccam').
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

    # 2. Construir filtro SQL / pre-filter si aplica
    filter_clauses = []
    if tema and tema.strip():
        clean_tema = tema.strip().replace("'", "''")
        filter_clauses.append(f"doc_topic = '{clean_tema}'")
    if documento_id and documento_id.strip():
        clean_doc_id = documento_id.strip().replace("'", "''")
        filter_clauses.append(f"doc_id = '{clean_doc_id}'")
        
    filter_expr = " AND ".join(filter_clauses) if filter_clauses else None

    results = []
    try:
        # Búsqueda vectorial
        query_builder = table.search(query_vector, query_type="vector")
        if filter_expr:
            query_builder = query_builder.where(filter_expr)
        
        raw_results = query_builder.limit(top_k * 2).to_list()
        
        for item in raw_results:
            # En LanceDB con distancia coseno: _distance va de 0.0 (idéntico) a 2.0 (opuesto)
            dist = item.get("_distance", 1.0)
            similarity = max(0.0, 1.0 - (dist / 2.0))
            
            if similarity >= min_score or len(results) < top_k:
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
                    "similarity": round(similarity, 4),
                    "distance": round(dist, 4)
                })
                
    except Exception as e:
        print(f"⚠️ [RAG Engine] Error en búsqueda vectorial LanceDB: {e}", file=sys.stderr)

    # Limitar a top_k
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
        
        return {
            "is_initialized": True,
            "total_chunks": total_chunks,
            "total_documents": len(docs_map),
            "documents": list(docs_map.values()),
            "topics": topics_list,
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
