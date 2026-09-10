"""
gateway/core/database.py - Conexión Canónica y Pool Singleton para MongoDB.
========================================================================
Centraliza la conexión a MongoDB mediante un MongoClient singleton con pool
de conexiones configurado, eliminando la creación repetitiva de clientes,
el churn de hilos y las demoras de handshake por petición.
"""
from pymongo import MongoClient
from config import get_mongo_uri, MONGO_DB

_shared_mongo_client = None


def get_mongo_client() -> MongoClient:
    """Retorna la instancia singleton de MongoClient compartida en todo el Gateway."""
    global _shared_mongo_client
    if _shared_mongo_client is None:
        _shared_mongo_client = MongoClient(
            get_mongo_uri(),
            serverSelectionTimeoutMS=1000,
            maxPoolSize=50,
            minPoolSize=5
        )
    return _shared_mongo_client


def get_db():
    """Retorna la base de datos principal de MongoDB usando el cliente compartido."""
    return get_mongo_client()[MONGO_DB]


def close_mongo_client():
    """Cierra limpiamente el cliente compartido de MongoDB si está abierto."""
    global _shared_mongo_client
    if _shared_mongo_client is not None:
        try:
            _shared_mongo_client.close()
        except Exception:
            pass
        _shared_mongo_client = None
