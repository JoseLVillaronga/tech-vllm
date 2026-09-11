"""
rag.config - Constantes, rutas y variables de entorno del subsistema RAG.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from config import API_KEY as MASTER_KEY, get_mongo_uri, MONGO_DB

load_dotenv()

PROJECT_DIR = str(Path(__file__).resolve().parent.parent)
LANCEDB_DIR = os.getenv("LANCEDB_PATH", os.path.join(PROJECT_DIR, "data", "lancedb"))
TABLE_NAME = os.getenv("LANCEDB_TABLE_NAME", "teccam_knowledge_base")
EMBEDDINGS_BACKEND_PORT = int(os.getenv("EMBEDDINGS_BACKEND_PORT", "18005"))

TECCAM_PDF_URL_BASE = os.getenv("TECCAM_PDF_URL_BASE", "http://127.0.0.1:5022").rstrip("/")
TECCAM_PDF_API_KEY = os.getenv("TECCAM_PDF_API_KEY", "").strip()

# Asegurar que el directorio de almacenamiento de LanceDB existe
os.makedirs(LANCEDB_DIR, exist_ok=True)

__all__ = [
    "PROJECT_DIR",
    "LANCEDB_DIR",
    "TABLE_NAME",
    "EMBEDDINGS_BACKEND_PORT",
    "MASTER_KEY",
    "get_mongo_uri",
    "MONGO_DB",
    "TECCAM_PDF_URL_BASE",
    "TECCAM_PDF_API_KEY"
]
