from pymongo import MongoClient
from config import get_mongo_uri, MONGO_DB


def get_db():
    """
    Retorna la instancia de base de datos MongoDB con timeout de 2000ms.
    """
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=2000)
    return client[MONGO_DB]

__all__ = ["get_db", "get_mongo_uri", "MONGO_DB"]
