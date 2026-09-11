"""
rag.db - Conexión persistente a LanceDB, esquema canónico PyArrow y CRUD multi-tenant.
"""

import sys
import re
from typing import List, Dict, Any, Optional
import pyarrow as pa
from .config import LANCEDB_DIR, TABLE_NAME

_db_instance = None


def get_lancedb():
    """Obtiene la instancia de conexión local de LanceDB."""
    global _db_instance
    if _db_instance is None:
        import lancedb
        _db_instance = lancedb.connect(LANCEDB_DIR)
    return _db_instance


def get_table(table_name: Optional[str] = None):
    """Obtiene la tabla de base de conocimiento (por defecto o específica por empresa) o None si no existe aún."""
    db = get_lancedb()
    target_name = table_name or TABLE_NAME
    try:
        res = db.list_tables()
        tables = res.tables if hasattr(res, "tables") else (res if isinstance(res, (list, set)) else db.table_names())
    except Exception:
        tables = db.table_names()
    if target_name in tables:
        return db.open_table(target_name)
    return None


def get_canonical_rag_schema():
    """Retorna el esquema PyArrow canónico oficial para las tablas LanceDB de la suite vLLM."""
    return pa.schema([
        pa.field("id", pa.string(), nullable=True),
        pa.field("doc_id", pa.string(), nullable=True),
        pa.field("doc_title", pa.string(), nullable=True),
        pa.field("doc_author", pa.string(), nullable=True),
        pa.field("doc_topic", pa.string(), nullable=True),
        pa.field("doc_date", pa.string(), nullable=True),
        pa.field("section_path", pa.string(), nullable=True),
        pa.field("chunk_index", pa.int64(), nullable=True),
        pa.field("chunk_tokens", pa.int64(), nullable=True),
        pa.field("total_chunks", pa.int64(), nullable=True),
        pa.field("total_doc_tokens", pa.int64(), nullable=True),
        pa.field("content", pa.string(), nullable=True),
        pa.field("text", pa.string(), nullable=True),
        pa.field("vector", pa.list_(pa.float32(), 1024), nullable=True),
        pa.field("doc_vigencia", pa.string(), nullable=False),
        pa.field("doc_fecha_publicacion", pa.string(), nullable=True),
    ])


def list_knowledge_bases() -> List[Dict[str, Any]]:
    """Lista todas las bases / tablas de conocimiento en LanceDB con sus metadatos y conteos."""
    db = get_lancedb()
    try:
        res = db.list_tables()
        table_names = res.tables if hasattr(res, "tables") else (res if isinstance(res, (list, set)) else db.table_names())
    except Exception:
        table_names = db.table_names()
    
    bases = []
    for name in sorted(table_names):
        try:
            tbl = db.open_table(name)
            count = len(tbl)
            df = tbl.to_arrow()
            doc_ids = set(df["doc_id"].to_pylist()) if "doc_id" in df.schema.names else set()
            topics = set(df["doc_topic"].to_pylist()) if "doc_topic" in df.schema.names else set()
            
            display_name = "TECCAM S.R.L. (Predeterminada)" if name == TABLE_NAME else name.replace("kb_", "").replace("_", " ").title()
            empresa = "TECCAM S.R.L." if name == TABLE_NAME else name.replace("kb_", "").replace("_", " ").title()
            bases.append({
                "table_name": name,
                "display_name": display_name,
                "empresa": empresa,
                "is_default": name == TABLE_NAME,
                "chunks_count": count,
                "docs_count": len(doc_ids),
                "topics": sorted([t for t in topics if t])
            })
        except Exception as e:
            print(f"⚠️ [RAG Engine] Error leyendo tabla {name}: {e}", file=sys.stderr)
            bases.append({
                "table_name": name,
                "display_name": name,
                "is_default": name == TABLE_NAME,
                "chunks_count": 0,
                "docs_count": 0,
                "topics": [],
                "error": str(e)
            })
    return bases


def create_knowledge_base(table_name: str, clone_from: Optional[str] = None, clone_themes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Crea una nueva tabla de conocimiento en LanceDB.
    Si se especifica clone_from y clone_themes, clona instantáneamente los fragmentos correspondientes
    desde la tabla origen en memoria (Apache Arrow), sin consumo de GPU ni reprocesamiento.
    Si la instalación es limpia desde cero y no hay bases previas, inicializa la tabla con el esquema canónico completo.
    """
    db = get_lancedb()
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name.strip().lower()).strip('_')
    if not clean_name:
        raise ValueError("El nombre de la tabla no es válido.")
    
    res = db.list_tables()
    existing_tables = res.tables if hasattr(res, "tables") else (res if isinstance(res, (list, set)) else db.table_names())
    if clean_name in existing_tables:
        raise ValueError(f"La base de conocimiento '{clean_name}' ya existe.")
        
    source_tbl = None
    if clone_from:
        source_tbl = get_table(clone_from)
        if source_tbl is None:
            raise ValueError(f"La tabla origen '{clone_from}' no existe.")
            
    if source_tbl is not None:
        if clone_themes and len(clone_themes) > 0:
            escaped_themes = [t.replace("'", "''") for t in clone_themes]
            theme_conditions = " OR ".join([f"doc_topic = '{t}'" for t in escaped_themes])
            arrow_data = source_tbl.search().where(theme_conditions).limit(100000).to_arrow()
            if len(arrow_data) > 0:
                new_tbl = db.create_table(clean_name, data=arrow_data)
                return {
                    "success": True,
                    "table_name": clean_name,
                    "chunks_cloned": len(arrow_data),
                    "cloned_from": clone_from,
                    "themes_cloned": clone_themes
                }
        schema = source_tbl.to_arrow().schema
        new_tbl = db.create_table(clean_name, schema=schema)
        return {
            "success": True,
            "table_name": clean_name,
            "chunks_cloned": 0,
            "cloned_from": clone_from,
            "themes_cloned": []
        }
    else:
        # Si no se pasó tabla origen o no existe tabla previa (ej: instalación desde cero)
        default_tbl = get_table(TABLE_NAME)
        if default_tbl is not None:
            schema = default_tbl.to_arrow().schema
        else:
            schema = get_canonical_rag_schema()
            
        new_tbl = db.create_table(clean_name, schema=schema)
        return {"success": True, "table_name": clean_name, "chunks_cloned": 0}


def clone_knowledge_domain(source_table: str, target_table: str, theme: str) -> Dict[str, Any]:
    """Clona un dominio de conocimiento desde una base a otra existente sin duplicar cómputo."""
    src = get_table(source_table)
    dst = get_table(target_table)
    if src is None:
        raise ValueError(f"Base origen '{source_table}' no encontrada.")
    if dst is None:
        raise ValueError(f"Base destino '{target_table}' no encontrada.")
        
    clean_theme = theme.replace("'", "''")
    arrow_data = src.search().where(f"doc_topic = '{clean_theme}'").limit(100000).to_arrow()
    if len(arrow_data) == 0:
        return {"success": True, "chunks_cloned": 0, "message": "No se encontraron fragmentos para este tema."}
        
    try:
        dst.delete(f"doc_topic = '{clean_theme}'")
    except Exception:
        pass
        
    dst.add(arrow_data)
    return {
        "success": True,
        "source_table": source_table,
        "target_table": target_table,
        "theme": theme,
        "chunks_cloned": len(arrow_data)
    }


def delete_knowledge_base(table_name: str) -> Dict[str, Any]:
    """Elimina una base de conocimiento en LanceDB, protegiendo siempre la base predeterminada de TECCAM S.R.L."""
    if table_name == TABLE_NAME:
        raise ValueError("No está permitido eliminar la base de conocimiento predeterminada (TECCAM S.R.L.).")
    db = get_lancedb()
    try:
        res = db.list_tables()
        tables = res.tables if hasattr(res, "tables") else (res if isinstance(res, (list, set)) else db.table_names())
        if table_name not in tables:
            raise ValueError(f"La base '{table_name}' no existe.")
        db.drop_table(table_name)
        return {"success": True, "deleted_table": table_name}
    except Exception as e:
        raise RuntimeError(f"Error al eliminar la base '{table_name}': {e}")


def get_rag_stats(table_name: Optional[str] = None) -> Dict[str, Any]:
    """Obtiene métricas y estadísticas globales de la base de conocimiento en LanceDB (predeterminada o por empresa)."""
    from .settings import get_rag_settings

    target_name = table_name or TABLE_NAME
    table = get_table(target_name)
    if table is None:
        return {
            "is_initialized": False,
            "total_chunks": 0,
            "total_documents": 0,
            "documents": [],
            "topics": [],
            "lancedb_path": LANCEDB_DIR,
            "table_name": target_name
        }
        
    try:
        total_chunks = len(table)
        df = table.to_arrow()
        
        doc_ids = df["doc_id"].to_pylist() if "doc_id" in df.schema.names else []
        doc_titles = df["doc_title"].to_pylist() if "doc_title" in df.schema.names else []
        doc_topics = df["doc_topic"].to_pylist() if "doc_topic" in df.schema.names else []
        doc_vigs = df["doc_vigencia"].to_pylist() if "doc_vigencia" in df.schema.names else ["NA (no aplica)"] * len(doc_ids)
        doc_fpubs = df["doc_fecha_publicacion"].to_pylist() if "doc_fecha_publicacion" in df.schema.names else [None] * len(doc_ids)
        
        docs_map = {}
        for d_id, d_title, d_topic, d_vig, d_fpub in zip(doc_ids, doc_titles, doc_topics, doc_vigs, doc_fpubs):
            if d_id not in docs_map:
                docs_map[d_id] = {
                    "id": d_id,
                    "title": d_title,
                    "topic": d_topic,
                    "vigencia": d_vig or "NA (no aplica)",
                    "fecha_publicacion": d_fpub or "",
                    "chunks_count": 0
                }
            docs_map[d_id]["chunks_count"] += 1
            
        topics_count = {}
        for t in doc_topics:
            if t:
                topics_count[t] = topics_count.get(t, 0) + 1
                
        topics_list = [{"name": k, "chunks_count": v} for k, v in topics_count.items()]

        vigencias_count = {}
        for d in docs_map.values():
            v = d.get("vigencia") or "NA (no aplica)"
            vigencias_count[v] = vigencias_count.get(v, 0) + 1
        
        rag_sett = get_rag_settings()
        return {
            "is_initialized": True,
            "enabled": rag_sett.get("enabled", True),
            "total_chunks": total_chunks,
            "total_documents": len(docs_map),
            "documents": list(docs_map.values()),
            "topics": topics_list,
            "vigencias_summary": vigencias_count,
            "active_topics": rag_sett.get("active_topics", []),
            "lancedb_path": LANCEDB_DIR,
            "table_name": target_name
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


__all__ = [
    "get_lancedb",
    "get_table",
    "get_canonical_rag_schema",
    "list_knowledge_bases",
    "create_knowledge_base",
    "clone_knowledge_domain",
    "delete_knowledge_base",
    "get_rag_stats"
]
