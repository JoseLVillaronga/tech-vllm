"""
rag.settings - Configuración global y persistencia en MongoDB de estados, dominios activos y modelos Cloud RAG.
"""

import sys
import time
from typing import Dict, Any, Optional, List
from .config import get_mongo_uri, MONGO_DB


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


__all__ = [
    "get_mongo_db",
    "get_rag_settings",
    "save_rag_settings"
]
