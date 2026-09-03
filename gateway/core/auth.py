import sys
from datetime import datetime, timezone
from fastapi import Request
from pymongo import MongoClient
from config import API_KEY as MASTER_KEY, get_mongo_uri, MONGO_DB


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


def extract_token(request: Request) -> str:
    """
    Extrae el token de autenticación desde múltiples cabeceras estándar
    (Authorization: Bearer, X-Api-Key, api-key, etc.) o parámetros de consulta.
    """
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    auth_header = auth_header.strip()

    x_api_key = (
        request.headers.get("x-api-key")
        or request.headers.get("X-Api-Key")
        or request.headers.get("X-API-Key")
        or request.headers.get("X-API-KEY")
        or request.headers.get("api-key")
        or request.headers.get("apikey")
        or request.headers.get("x-auth-token")
        or ""
    ).strip()

    token = ""
    if auth_header:
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        elif auth_header.lower().startswith("api-key "):
            token = auth_header.split(" ", 1)[1].strip()
        else:
            token = auth_header
    elif x_api_key:
        token = x_api_key
    else:
        token = (
            request.query_params.get("api_key")
            or request.query_params.get("token")
            or request.query_params.get("key")
            or ""
        ).strip()

    return token


def get_key_doc(token: str):
    """
    Recupera el documento de la clave API desde MongoDB y procesa
    los reinicios periódicos de cuota (Diario / Mensual).
    """
    if token == MASTER_KEY:
        return {
            "name": "Master Key",
            "services": ["gemma", "gemma_raw", "whisper", "tts", "diarization", "embeddings", "image", "docling"],
            "allowed_providers": ["*"],
            "is_active": True
        }
    try:
        db = get_db()
        key_doc = db.api_keys.find_one({"key": token, "is_active": True})
        if not key_doc:
            return None

        # Evaluación de reinicio periódico de cupo de tokens (Diario / Mensual)
        quota_reset = key_doc.get("quota_reset", "none")
        if quota_reset in ["daily", "monthly"]:
            last_reset_at = key_doc.get("last_reset_at")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            reset_needed = False

            if not last_reset_at:
                reset_needed = True
            else:
                if isinstance(last_reset_at, str):
                    try:
                        last_dt = datetime.fromisoformat(last_reset_at.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        last_dt = now
                elif isinstance(last_reset_at, datetime):
                    last_dt = last_reset_at.replace(tzinfo=None)
                else:
                    last_dt = now

                if quota_reset == "daily":
                    if now.date() > last_dt.date():
                        reset_needed = True
                elif quota_reset == "monthly":
                    if (now.year, now.month) > (last_dt.year, last_dt.month):
                        reset_needed = True

            if reset_needed:
                db.api_keys.update_one(
                    {"_id": key_doc["_id"]},
                    {"$set": {"used_tokens": 0, "last_reset_at": now}}
                )
                key_doc["used_tokens"] = 0
                key_doc["last_reset_at"] = now
                print(f"🔄 Gateway: Cupo de tokens reiniciado automáticamente ({quota_reset}) para la clave '{key_doc.get('name')}'", flush=True)

        return key_doc
    except Exception as e:
        print(f"⚠️ Error al consultar token en MongoDB: {e}", file=sys.stderr)
        return None


def validate_token_doc(key_doc: dict, service_name: str) -> bool:
    """
    Verifica que el documento de clave tenga permisos para el servicio solicitado
    y no haya expirado.
    """
    if not key_doc:
        return False
    if key_doc.get("name") == "Master Key":
        return True

    # Validar permisos de servicio / proveedores
    allowed_services = key_doc.get("services", [])
    allowed_providers = key_doc.get("allowed_providers", [])

    if service_name in ["gemma", "gemma_raw"]:
        # En los proxies LLM (puerto 8000 o 8010), se permite el paso si la clave tiene
        # el servicio específico habilitado (gemma o gemma_raw) o proveedores en la nube
        if service_name not in allowed_services and not allowed_providers:
            return False
    else:
        if service_name not in allowed_services:
            return False

    # Validar expiración
    expires_at = key_doc.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            expires_dt = expires_at

        if expires_dt.tzinfo is not None:
            now = datetime.now(expires_dt.tzinfo)
        else:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

        if now > expires_dt:
            return False

    return True


def validate_token(token: str, service_name: str) -> bool:
    key_doc = get_key_doc(token)
    return validate_token_doc(key_doc, service_name)
