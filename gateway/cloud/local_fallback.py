import os
import sys
import time
import asyncio
import httpx
from typing import Tuple, Optional, Dict, Any
from config import env as get_env_setting
from gateway.core.database import get_db
from gateway.cloud.cloud_sync import slugify_provider_name

# Estado en memoria (Disyuntor / Circuit Breaker Desacoplado)
_local_engine_healthy: bool = True
_local_fallback_lock = asyncio.Lock()


def is_local_fallback_enabled() -> bool:
    """
    Verifica si el fallback del motor local a la nube está habilitado en .env.
    """
    val = get_env_setting("LOCAL_FALLBACK_ENABLED", "false").strip().lower()
    return val in ("true", "1", "yes")


def get_local_fallback_config() -> Tuple[str, str, float, float]:
    """
    Retorna la configuración completa del fallback:
    (provider_id, target_model, check_interval_sec, connect_timeout_sec).
    """
    prov_id = get_env_setting("LOCAL_FALLBACK_PROVIDER_ID", "").strip()
    model = get_env_setting("LOCAL_FALLBACK_MODEL", "").strip()
    
    try:
        check_interval = float(get_env_setting("LOCAL_FALLBACK_CHECK_INTERVAL", "60"))
    except (ValueError, TypeError):
        check_interval = 60.0

    try:
        connect_timeout = float(get_env_setting("LOCAL_FALLBACK_CONNECT_TIMEOUT", "1.0"))
    except (ValueError, TypeError):
        connect_timeout = 1.0

    return prov_id, model, max(check_interval, 5.0), max(connect_timeout, 0.1)


def is_local_engine_healthy() -> bool:
    """
    Consulta en memoria (0 delay) el estado de disponibilidad del motor local.
    """
    return _local_engine_healthy


def mark_local_engine_down():
    """
    Activa de inmediato el disyuntor en memoria: marca el motor local como no disponible.
    """
    global _local_engine_healthy
    if _local_engine_healthy:
        print("⚠️ [Circuit Breaker] Motor local declarado NO DISPONIBLE. Activando conmutación a Fallback Cloud.", flush=True)
    _local_engine_healthy = False


def mark_local_engine_up():
    """
    Restaura el disyuntor en memoria: marca el motor local como recuperado.
    """
    global _local_engine_healthy
    if not _local_engine_healthy:
        print("✅ [Circuit Breaker] Motor local (:18100) recuperado y operativo. Restableciendo tráfico a la GPU local.", flush=True)
    _local_engine_healthy = True


def get_local_fallback_target() -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Obtiene la información de conexión del proveedor cloud y el modelo de destino para el fallback.
    Retorna (dict_proveedor, modelo_destino).
    """
    prov_id, target_model, _, _ = get_local_fallback_config()
    db = get_db()
    prov_obj = None

    if prov_id:
        try:
            from bson import ObjectId
            prov_obj = db.cloud_providers.find_one({"_id": ObjectId(prov_id), "is_active": True})
        except Exception:
            prov_obj = db.cloud_providers.find_one({"_id": prov_id, "is_active": True})

    # Si no se configuró o no se encontró el proveedor por ID, utilizar el primer proveedor activo
    if not prov_obj:
        prov_obj = db.cloud_providers.find_one({"is_active": True})

    if not prov_obj:
        return None, ""

    p_slug = slugify_provider_name(prov_obj.get("name", "cloud"))
    fallback_model = target_model or "default"

    cloud_provider_info = {
        "provider_id": str(prov_obj["_id"]),
        "provider_name": prov_obj.get("name", ""),
        "provider_slug": p_slug,
        "base_url": prov_obj.get("base_url", "").rstrip("/"),
        "api_key": prov_obj.get("api_key", ""),
        "raw_model_id": fallback_model
    }
    return cloud_provider_info, fallback_model


async def local_fallback_monitor_loop():
    """
    Lazo en segundo plano desacoplado:
    Verifica periódicamente el estado de salud del motor local en :18100.
    Cuando el motor responde 200 OK, reactiva en memoria el tráfico local sin penalizar peticiones.
    """
    print("🛡️ Monitor en segundo plano de Alta Disponibilidad (Local Fallback Circuit Breaker) iniciado.", flush=True)

    while True:
        try:
            prov_id, target_model, check_interval, connect_timeout = get_local_fallback_config()
            backend_port = int(get_env_setting("GEMMA_BACKEND_PORT", get_env_setting("LLAMA_PORT", "18100")))

            is_up = False
            try:
                # Sonda liviana con connect timeout estricto (no bloqueante)
                req_timeout = httpx.Timeout(timeout=connect_timeout + 1.5, connect=connect_timeout)
                async with httpx.AsyncClient(timeout=req_timeout) as client:
                    resp = await client.get(f"http://127.0.0.1:{backend_port}/health")
                    if resp.status_code == 200:
                        is_up = True
                    elif resp.status_code == 404:
                        # Fallback a /v1/models para motores que no exponen /health
                        resp_models = await client.get(f"http://127.0.0.1:{backend_port}/v1/models")
                        if resp_models.status_code == 200:
                            is_up = True
            except Exception:
                is_up = False

            if is_up:
                mark_local_engine_up()
            else:
                if is_local_fallback_enabled():
                    mark_local_engine_down()

            await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ Error en bucle monitor local fallback: {e}", file=sys.stderr, flush=True)
            await asyncio.sleep(60)
