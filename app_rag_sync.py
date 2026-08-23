#!/usr/bin/env python3
"""
app_rag_sync.py - Sincronizador Diferencial de Base de Conocimiento Teccam PDF -> LanceDB
========================================================================================
Sincroniza periódica o manualmente los documentos desde la API de Teccam PDF (:5022),
los trocea con chunking jerárquico respetando tablas y secciones, genera vectores de 1024D
con Qwen3-Embedding (:18005) y los persiste indexados en LanceDB.
"""

import os
import sys
import time
import json
import argparse
import hashlib
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Rutas del proyecto
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LANCEDB_DIR = os.getenv("LANCEDB_PATH", os.path.join(PROJECT_DIR, "data", "lancedb"))
TABLE_NAME = os.getenv("LANCEDB_TABLE_NAME", "teccam_knowledge_base")

# Configuración de Teccam PDF
TECCAM_PDF_URL_BASE = os.getenv("TECCAM_PDF_URL_BASE", "http://192.168.1.33:5022").rstrip("/")
TECCAM_PDF_API_KEY = os.getenv("TECCAM_PDF_API_KEY", "").strip()

# Importar motor RAG y embeddings
from rag_engine import get_lancedb, get_table, generate_embeddings_batch

# Helper para MongoDB
def get_mongo_db():
    try:
        from pymongo import MongoClient
        user = os.getenv("MONGO_USER", "admin")
        password = os.getenv("MONGO_PASS", "joseMDB365$")
        host = os.getenv("MONGO_HOST", "127.0.0.1")
        db_name = os.getenv("MONGO_DB", "vllm")
        uri = f"mongodb://{user}:{password}@{host}:27017/{db_name}?authSource=admin"
        client = MongoClient(uri, serverSelectionTimeoutMS=1500)
        return client[db_name]
    except Exception as e:
        print(f"⚠️ [Sync] No se pudo conectar a MongoDB para logging: {e}", file=sys.stderr)
        return None

def log_sync_to_mongo(log_data: Dict[str, Any]):
    """Guarda un registro histórico de la sincronización en MongoDB."""
    db = get_mongo_db()
    if db is not None:
        try:
            db.rag_sync_logs.insert_one(log_data)
        except Exception as e:
            print(f"⚠️ [Sync] Error guardando log en MongoDB: {e}", file=sys.stderr)

def hierarchical_chunk_markdown(text: str, max_chars: int = 1200, min_chars: int = 100) -> List[Dict[str, str]]:
    """
    Trocea un texto en Markdown preservando la jerarquía de títulos y tablas.
    
    Returns:
        Lista de dicts: [{'section': 'H1 > H2 > H3', 'content': '...'}]
    """
    lines = text.split('\n')
    chunks = []
    
    current_h1 = ''
    current_h2 = ''
    current_h3 = ''
    current_buffer = []
    current_len = 0
    in_table = False
    
    def get_section_path():
        parts = [p for p in [current_h1, current_h2, current_h3] if p]
        return ' > '.join(parts) if parts else 'Sección General'
        
    def flush_buffer():
        nonlocal current_buffer, current_len
        if not current_buffer:
            return
        content = '\n'.join(current_buffer).strip()
        if content:
            chunks.append({
                'section': get_section_path(),
                'content': content
            })
        current_buffer = []
        current_len = 0
        
    for line in lines:
        stripped = line.strip()
        
        # Detectar tablas Markdown
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
        else:
            in_table = False
            
        # Detectar encabezados (solo si no estamos dentro de una celda de tabla)
        if not in_table:
            if stripped.startswith('# '):
                flush_buffer()
                current_h1 = stripped[2:].strip()
                current_h2 = ''
                current_h3 = ''
                continue
            elif stripped.startswith('## '):
                flush_buffer()
                current_h2 = stripped[3:].strip()
                current_h3 = ''
                continue
            elif stripped.startswith('### '):
                flush_buffer()
                current_h3 = stripped[4:].strip()
                continue
            
        line_len = len(line) + 1
        
        # Si el búfer supera el tamaño máximo y no estamos en medio de una tabla
        if current_len + line_len > max_chars and current_buffer and not in_table:
            flush_buffer()
            
        current_buffer.append(line)
        current_len += line_len
        
    flush_buffer()
    
    # Post-procesamiento: Fusionar micro-chunks (< min_chars) con el chunk anterior si comparten sección
    merged_chunks = []
    for ch in chunks:
        if merged_chunks and len(ch['content']) < min_chars and merged_chunks[-1]['section'] == ch['section']:
            merged_chunks[-1]['content'] += "\n\n" + ch['content']
        else:
            merged_chunks.append(ch)
            
    return merged_chunks

def fetch_teccam_documents_index() -> List[Dict[str, Any]]:
    """Consulta la API de Teccam PDF y retorna el listado completo de documentos disponibles."""
    if not TECCAM_PDF_URL_BASE:
        raise ValueError("TECCAM_PDF_URL_BASE no está configurada en .env")
        
    url = f"{TECCAM_PDF_URL_BASE}/api/v1/rag/documentos"
    headers = {}
    if TECCAM_PDF_API_KEY:
        headers["Authorization"] = f"Bearer {TECCAM_PDF_API_KEY}"
        
    all_docs = []
    page = 1
    limit = 100
    
    with httpx.Client(timeout=30.0) as client:
        while True:
            params = {"pagina": page, "limite": limit}
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"Error HTTP {resp.status_code} al consultar índice Teccam PDF: {resp.text}")
                
            data = resp.json()
            docs = data.get("documentos", [])
            if not docs:
                break
                
            all_docs.extend(docs)
            total_pages = data.get("total_paginas", 1)
            if page >= total_pages:
                break
            page += 1
            
    return all_docs

def fetch_teccam_document_detail(doc_id: str) -> Dict[str, Any]:
    """Obtiene el contenido completo en Markdown y metadatos de un documento específico."""
    url = f"{TECCAM_PDF_URL_BASE}/api/v1/rag/documentos/{doc_id}"
    headers = {}
    if TECCAM_PDF_API_KEY:
        headers["Authorization"] = f"Bearer {TECCAM_PDF_API_KEY}"
        
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Error HTTP {resp.status_code} al descargar documento {doc_id}: {resp.text}")
        return resp.json()

def sync_knowledge_base(force: bool = False, doc_id_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Ejecuta el ciclo de sincronización diferencial contra Teccam PDF.
    
    Args:
        force: Si es True, re-indexa todos los documentos ignorando el estado previo.
        doc_id_filter: Si se especifica, sincroniza únicamente ese documento.
        
    Returns:
        Diccionario con el resumen de la operación.
    """
    start_time = time.time()
    sync_date = datetime.utcnow()
    
    print("=" * 70)
    print(f"🔄 [RAG Sync] Iniciando Sincronizador Teccam PDF -> LanceDB")
    print(f"🌐 Servidor Teccam: {TECCAM_PDF_URL_BASE}")
    print(f"📁 Directorio LanceDB: {LANCEDB_DIR}")
    print(f"⚙️ Modo: {'Forzado (Re-indexación completa)' if force else 'Diferencial / Incremental'}")
    print("=" * 70)
    
    db = get_lancedb()
    table = get_table()
    
    # 1. Obtener índice de documentos remotos
    try:
        remote_docs = fetch_teccam_documents_index()
        print(f"📚 Documentos remotos encontrados en Teccam PDF: {len(remote_docs)}")
    except Exception as e:
        err_msg = f"No se pudo consultar la API de Teccam PDF: {e}"
        print(f"❌ [RAG Sync] {err_msg}", file=sys.stderr)
        log_sync_to_mongo({
            "timestamp": sync_date,
            "status": "error",
            "error": err_msg,
            "duration_sec": time.time() - start_time
        })
        return {"success": False, "error": err_msg}
        
    if doc_id_filter:
        remote_docs = [d for d in remote_docs if d.get("id") == doc_id_filter]
        if not remote_docs:
            print(f"⚠️ No se encontró el documento ID '{doc_id_filter}' en Teccam PDF.")
            return {"success": False, "error": f"Documento ID {doc_id_filter} no encontrado"}

    # 2. Mapear documentos ya indexados localmente en LanceDB
    local_doc_dates = {}
    if table is not None and not force:
        try:
            df = table.to_arrow()
            if "doc_id" in df.schema.names and "doc_date" in df.schema.names:
                for d_id, d_date in zip(df["doc_id"].to_pylist(), df["doc_date"].to_pylist()):
                    local_doc_dates[d_id] = d_date
        except Exception as e:
            print(f"⚠️ [RAG Sync] Advertencia leyendo estado de LanceDB: {e}", file=sys.stderr)

    docs_to_sync = []
    docs_to_delete = []
    
    remote_ids = set()
    for doc in remote_docs:
        d_id = doc.get("id")
        remote_ids.add(d_id)
        d_date = doc.get("fecha_creacion", "")
        
        # Si es nuevo, o cambió de fecha o forzamos re-indexación
        if force or (d_id not in local_doc_dates) or (local_doc_dates.get(d_id) != d_date):
            docs_to_sync.append(doc)
            
    # Detectar documentos eliminados remotamente
    if not doc_id_filter:
        for local_id in local_doc_dates.keys():
            if local_id not in remote_ids:
                docs_to_delete.append(local_id)

    print(f"📦 Documentos a procesar/actualizar: {len(docs_to_sync)}")
    print(f"🗑️ Documentos obsoletos a purgar:    {len(docs_to_delete)}")
    
    # 3. Eliminar documentos obsoletos en LanceDB
    if table is not None and docs_to_delete:
        for del_id in docs_to_delete:
            try:
                table.delete(f"doc_id = '{del_id}'")
                print(f"   🗑️ Purgado documento ID: {del_id}")
            except Exception as de:
                print(f"   ⚠️ Error eliminando {del_id}: {de}", file=sys.stderr)

    # 4. Procesar y vectorizar cada documento nuevo/modificado
    synced_details = []
    total_new_chunks = 0
    all_table_records = []
    
    for idx, doc in enumerate(docs_to_sync, 1):
        doc_id = doc.get("id")
        doc_title = doc.get("titulo", "Sin título")
        doc_author = doc.get("autor", "Desconocido")
        doc_topic = doc.get("tema", "General")
        doc_date = doc.get("fecha_creacion", "")
        
        print(f"\n📖 [{idx}/{len(docs_to_sync)}] Descargando '{doc_title}' ({doc_topic})...")
        try:
            detail = fetch_teccam_document_detail(doc_id)
            raw_markdown = detail.get("texto", "")
            if not raw_markdown.strip():
                print(f"   ⚠️ El documento '{doc_title}' está vacío. Omitiendo.")
                continue
                
            # Chunking jerárquico
            chunks = hierarchical_chunk_markdown(raw_markdown)
            print(f"   ✂️ Troceado en {len(chunks)} fragmentos estructurados.")
            
            # Preparar textos enriquecidos para embedding y lectura del LLM
            enriched_texts = []
            chunk_records = []
            
            for c_idx, ch in enumerate(chunks):
                section = ch["section"]
                content = ch["content"]
                
                # Contexto enriquecido para alta densidad semántica
                enriched = (
                    f"DOCUMENTO: {doc_title}\n"
                    f"TEMA: {doc_topic}\n"
                    f"SECCIÓN: {section}\n"
                    f"AUTOR: {doc_author}\n\n"
                    f"{content}"
                )
                enriched_texts.append(enriched)
                
                chunk_id = f"{doc_id}_{c_idx:04d}"
                chunk_records.append({
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "doc_author": doc_author,
                    "doc_topic": doc_topic,
                    "doc_date": doc_date,
                    "section_path": section,
                    "chunk_index": c_idx,
                    "content": content,
                    "text": enriched
                })
                
            # Generar vectores con Qwen3-Embedding en lotes seguros
            print(f"   🧠 Vectorizando {len(enriched_texts)} fragmentos con Qwen3-Embedding...")
            vectors = generate_embeddings_batch(enriched_texts, batch_size=16, timeout=30.0)
            
            # Asignar vector a cada registro
            for rec, vec in zip(chunk_records, vectors):
                rec["vector"] = vec
                
            # Si la tabla aún no existe, crearla con este primer documento
            if table is None:
                table = db.create_table(TABLE_NAME, data=chunk_records, mode="overwrite")
                print(f"   💾 Tabla '{TABLE_NAME}' creada e inicializada.")
            else:
                # Si el documento ya existía previamente en LanceDB, eliminar sus versiones anteriores
                if doc_id in local_doc_dates:
                    try:
                        table.delete(f"doc_id = '{doc_id}'")
                    except Exception:
                        pass
                table.add(chunk_records)
                print(f"   💾 {len(chunk_records)} fragmentos guardados en LanceDB.")
                    
            total_new_chunks += len(chunk_records)
            synced_details.append({
                "doc_id": doc_id,
                "title": doc_title,
                "topic": doc_topic,
                "chunks_count": len(chunk_records)
            })
            print(f"   ✅ Vectorización e indexación completa ({len(chunk_records)} chunks).")
            
        except Exception as doc_err:
            print(f"   ❌ Error procesando documento '{doc_title}': {doc_err}", file=sys.stderr)

    # 5. Recrear / Actualizar índice FTS para búsqueda de texto completo si hubo cambios
    if total_new_chunks > 0 and table is not None:
        try:
            table.create_fts_index("text", replace=True)
            print("🔍 Índice FTS (Full-Text Search) actualizado en LanceDB.")
        except Exception as fts_err:
            print(f"⚠️ Nota sobre índice FTS: {fts_err}")

    duration_sec = round(time.time() - start_time, 2)
    current_table = get_table()
    total_chunks_in_db = len(current_table) if current_table else 0
    
    print("=" * 70)
    print(f"🎉 Sincronización finalizada en {duration_sec} segundos!")
    print(f"📊 Documentos sincronizados en esta ejecución: {len(synced_details)}")
    print(f"📦 Total de fragmentos indexados en LanceDB:   {total_chunks_in_db}")
    print("=" * 70)
    
    result_summary = {
        "success": True,
        "timestamp": sync_date.isoformat(),
        "duration_sec": duration_sec,
        "docs_synced_count": len(synced_details),
        "docs_synced": synced_details,
        "docs_purged_count": len(docs_to_delete),
        "total_chunks_in_db": total_chunks_in_db,
        "lancedb_path": LANCEDB_DIR
    }
    
    # Registrar log en MongoDB
    log_sync_to_mongo(result_summary)
    return result_summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincronizador Teccam PDF -> LanceDB")
    parser.add_argument("--force", action="store_true", help="Re-indexar todos los documentos desde cero")
    parser.add_argument("--doc-id", type=str, default=None, help="Sincronizar un único documento por su ID")
    args = parser.parse_args()
    
    sync_knowledge_base(force=args.force, doc_id_filter=args.doc_id)
