import re
import sys
import asyncio
import httpx
from pymongo import MongoClient
from config import get_mongo_uri, MONGO_DB

cached_cloud_models = {}         # Mapeo 'provider_slug/m_id' -> dict de información del proveedor
cached_cloud_models_by_raw = {}  # Mapeo 'm_id' -> lista de dicts de información de proveedores
cached_cloud_models_lock = asyncio.Lock()


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


def slugify_provider_name(name: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9_\-]+', '_', name.strip().lower()).strip('_')
    return slug or "cloud"


async def sync_cloud_providers_loop():
    """
    Lazo en segundo plano para sincronizar el catálogo de modelos
    desde proveedores externos en la nube registrados en MongoDB.
    """
    global cached_cloud_models, cached_cloud_models_by_raw
    print("☁️ Sincronizador de modelos externos en la nube del Gateway Iniciado.", flush=True)
    while True:
        try:
            db = get_db()
            providers = list(db.cloud_providers.find({"is_active": True}))

            new_cloud_models = {}
            new_cloud_models_by_raw = {}
            for p in providers:
                provider_id = str(p["_id"])
                name = p.get("name", "Desconocido")
                provider_slug = slugify_provider_name(name)
                base_url = p.get("base_url", "").rstrip("/")
                api_key = p.get("api_key", "")

                if not base_url or not api_key:
                    continue

                try:
                    # Usar un cliente temporal rápido para no retrasar la sincronización de otros
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        headers = {"Authorization": f"Bearer {api_key}"}
                        resp = await client.get(f"{base_url}/models", headers=headers)
                        if resp.status_code == 200:
                            models_data = resp.json()
                            for m in models_data.get("data", []):
                                m_id = m.get("id")
                                if m_id:
                                    provider_info = {
                                        "provider_id": provider_id,
                                        "provider_name": name,
                                        "provider_slug": provider_slug,
                                        "raw_model_id": m_id,
                                        "base_url": base_url,
                                        "api_key": api_key
                                    }
                                    # Registro con prefijo único por proveedor (ej: 'openrouter/anthropic/claude-3.5-sonnet')
                                    prefixed_id = f"{provider_slug}/{m_id}"
                                    new_cloud_models[prefixed_id] = provider_info

                                    # Registro por nombre nativo (para resolución retrocompatible inteligente)
                                    if m_id not in new_cloud_models_by_raw:
                                        new_cloud_models_by_raw[m_id] = []
                                    new_cloud_models_by_raw[m_id].append(provider_info)
                except Exception as p_err:
                    print(f"⚠️ Gateway: Error obteniendo modelos del proveedor '{name}': {p_err}", file=sys.stderr, flush=True)

            async with cached_cloud_models_lock:
                cached_cloud_models = new_cloud_models
                cached_cloud_models_by_raw = new_cloud_models_by_raw

        except Exception as e:
            print(f"⚠️ Error al sincronizar proveedores en la nube: {e}", file=sys.stderr, flush=True)

        await asyncio.sleep(60)
