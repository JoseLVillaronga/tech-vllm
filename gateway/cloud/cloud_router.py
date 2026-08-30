import os
import sys
import json
import time
import httpx
from datetime import datetime
from fastapi import Response, HTTPException, status
from pymongo import MongoClient
from config import API_KEY as MASTER_KEY, get_mongo_uri, MONGO_DB, env
from gateway.cloud.cloud_sync import cached_cloud_models, cached_cloud_models_by_raw, cached_cloud_models_lock, slugify_provider_name


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


# Alias unificado hacia config.env
get_env_setting = env


async def handle_models_list(token: str, key_doc: dict, current_target_port: int) -> Response:
    """
    Manejador para GET /v1/models unificando modelos locales y externos según permisos.
    """
    try:
        is_master = (token == MASTER_KEY)
        allowed_services = key_doc.get("services", []) if key_doc else []
        key_allowed_providers = key_doc.get("allowed_providers", []) if key_doc else []

        combined_models = []
        # 1. Modelos locales expuestos con prefijo 'local/'
        if is_master or ("gemma" in allowed_services):
            try:
                async with httpx.AsyncClient(timeout=3.0) as temp_cli:
                    headers_local = {"Authorization": f"Bearer {MASTER_KEY}"}
                    resp_local = await temp_cli.get(f"http://127.0.0.1:{current_target_port}/v1/models", headers=headers_local)
                    if resp_local.status_code == 200:
                        local_data = resp_local.json().get("data", [])
                        for lm in local_data:
                            raw_id = lm.get("id", "")
                            prefixed_id = f"local/{raw_id}" if not raw_id.startswith("local/") else raw_id
                            combined_models.append({
                                "id": prefixed_id,
                                "object": "model",
                                "created": lm.get("created", int(time.time())),
                                "owned_by": "local"
                            })

                        # Si la búsqueda web está configurada, exponer también el modelo virtual local/gemma-4-web
                        ollama_api_key = get_env_setting("OLLAMA_API_KEY", "").strip()
                        ollama_search_on = get_env_setting("OLLAMA_SEARCH_ENABLED", "true").strip().lower() in ["true", "1", "yes"]
                        if ollama_search_on and ollama_api_key:
                            combined_models.append({
                                "id": "local/gemma-4-web",
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": "local-web-search"
                            })

                        # Exponer modelo virtual local/gemma-4-rag (Base de Conocimiento LanceDB)
                        combined_models.append({
                            "id": "local/gemma-4-rag",
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "local-rag-lancedb"
                        })

                        # Exponer modelo virtual cloud-rag (Base de Conocimiento LanceDB + Proveedor en la Nube)
                        combined_models.append({
                            "id": "cloud-rag",
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "cloud-rag-lancedb"
                        })
                        combined_models.append({
                            "id": "local/cloud-rag",
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "cloud-rag-lancedb"
                        })

                        # Si tiene permiso de embeddings, exponer también el modelo de embeddings
                        if is_master or ("embeddings" in allowed_services):
                            combined_models.append({
                                "id": "Qwen/Qwen3-Embedding-0.6B",
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": "local-embeddings"
                            })
                            combined_models.append({
                                "id": "text-embedding-3-small",
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": "openai-alias"
                            })

                        # Si tiene permiso de imagen, exponer también el modelo de generación de imágenes
                        if is_master or ("image" in allowed_services):
                            img_model = get_env_setting("IMAGE_MODEL", "stabilityai/sdxl-turbo")
                            combined_models.append({
                                "id": img_model,
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": "local-diffusion"
                            })
                            combined_models.append({
                                "id": "local/image-generator",
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": "local-diffusion"
                            })
            except Exception as le:
                print(f"⚠️ Gateway: Error obteniendo modelos locales: {le}", file=sys.stderr, flush=True)

        # 2. Modelos de proveedores en la nube expuestos
        if is_master:
            # Master Key ve todos los modelos de proveedores activos en caché
            async with cached_cloud_models_lock:
                for pref_id, p_info in cached_cloud_models.items():
                    prov_name = p_info.get("provider_name", "")
                    combined_models.append({
                        "id": pref_id,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": prov_name
                    })
        elif key_doc:
            # Clave secundaria: consultar modelos granulares autorizados en MongoDB
            try:
                db = get_db()
                key_models = list(db.api_key_models.find({"key_id": key_doc["_id"]}))
                if key_models:
                    for km in key_models:
                        pref_id = km.get("prefixed_id") or f"{km.get('provider_slug')}/{km.get('model_id')}"
                        prov_name = km.get("provider_name", "cloud")
                        combined_models.append({
                            "id": pref_id,
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": prov_name
                        })
                else:
                    # Fallback retrocompatible para claves sin modelos granulares guardados
                    async with cached_cloud_models_lock:
                        for pref_id, p_info in cached_cloud_models.items():
                            prov_id = p_info.get("provider_id", "")
                            prov_name = p_info.get("provider_name", "")
                            prov_slug = p_info.get("provider_slug", "")
                            if ("*" in key_allowed_providers) or (prov_id in key_allowed_providers) or (prov_name in key_allowed_providers) or (prov_slug in key_allowed_providers):
                                combined_models.append({
                                    "id": pref_id,
                                    "object": "model",
                                    "created": int(time.time()),
                                    "owned_by": prov_name
                                })
            except Exception as me:
                print(f"⚠️ Gateway: Error obteniendo modelos cloud para clave: {me}", file=sys.stderr, flush=True)

        return Response(
            content=json.dumps({"object": "list", "data": combined_models}),
            media_type="application/json",
            status_code=200
        )
    except Exception as e:
        print(f"⚠️ Gateway: Error al combinar /v1/models: {e}", file=sys.stderr, flush=True)
        return Response(
            content=json.dumps({"object": "list", "data": []}),
            media_type="application/json",
            status_code=500
        )


async def resolve_cloud_model(req_model: str, token: str, key_doc: dict) -> tuple:
    """
    Determina si la petición corresponde a un modelo en la nube o local,
    y retorna (is_cloud_request, actual_model, cloud_provider, apply_rag_injection, base_vllm_model).
    """
    is_master = (token == MASTER_KEY)
    allowed_services = key_doc.get("services", []) if key_doc else []
    key_allowed_providers = key_doc.get("allowed_providers", []) if key_doc else []

    is_cloud_request = False
    cloud_provider = None
    actual_model = req_model
    apply_rag_injection = False
    base_vllm_model = None

    if req_model in ["local/gemma-4-web", "gemma-4-web"]:
        is_cloud_request = False
        actual_model = "gemma-4-web"
        base_vllm_model = get_env_setting("MODEL", "google/gemma-4-E4B-it").strip('"').strip("'")
    elif req_model in ["local/gemma-4-rag", "gemma-4-rag"]:
        is_cloud_request = False
        actual_model = "gemma-4-rag"
        apply_rag_injection = True
        base_vllm_model = get_env_setting("MODEL", "google/gemma-4-E4B-it").strip('"').strip("'")
    elif req_model in ["cloud-rag", "local/cloud-rag", "cloud/rag"]:
        from rag_engine import get_rag_settings
        rag_sett = get_rag_settings()
        c_prov_id = rag_sett.get("cloud_rag_provider_id")
        c_model_id = rag_sett.get("cloud_rag_model_id")

        db = get_db()
        prov_obj = None
        if c_prov_id:
            try:
                from bson import ObjectId
                prov_obj = db.cloud_providers.find_one({"_id": ObjectId(c_prov_id), "is_active": True})
            except Exception:
                prov_obj = db.cloud_providers.find_one({"_id": c_prov_id, "is_active": True})

        if not prov_obj:
            prov_obj = db.cloud_providers.find_one({"is_active": True})

        if not prov_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay ningún proveedor en la nube configurado o activo en la suite para 'cloud-rag'. Configúralo en la pestaña Base RAG del Dashboard."
            )

        p_slug = slugify_provider_name(prov_obj.get("name", "cloud"))
        target_cloud_model = c_model_id or "default"

        is_cloud_request = True
        cloud_provider = {
            "provider_id": str(prov_obj["_id"]),
            "provider_name": prov_obj.get("name", ""),
            "provider_slug": p_slug,
            "base_url": prov_obj.get("base_url", ""),
            "api_key": prov_obj.get("api_key", ""),
            "raw_model_id": target_cloud_model
        }
        actual_model = target_cloud_model
        apply_rag_injection = True
    elif req_model.startswith("local/"):
        is_cloud_request = False
        actual_model = req_model[6:]
    else:
        clean_req_model = req_model
        if req_model.endswith("-rag") and req_model not in ["gemma-4-rag", "cloud-rag"]:
            clean_req_model = req_model[:-4]
            apply_rag_injection = True
        elif req_model.endswith(":rag"):
            clean_req_model = req_model[:-4]
            apply_rag_injection = True

        matched_cloud = False
        if not is_master and key_doc:
            try:
                db = get_db()
                matched_km = db.api_key_models.find_one({
                    "key_id": key_doc["_id"],
                    "$or": [
                        {"prefixed_id": clean_req_model},
                        {"model_id": clean_req_model}
                    ]
                })
                if matched_km:
                    p_id = matched_km.get("provider_id")
                    prov_obj = db.cloud_providers.find_one({"_id": p_id, "is_active": True})
                    if prov_obj:
                        is_cloud_request = True
                        cloud_provider = {
                            "provider_id": str(prov_obj["_id"]),
                            "provider_name": prov_obj.get("name", ""),
                            "provider_slug": matched_km.get("provider_slug") or slugify_provider_name(prov_obj.get("name", "")),
                            "base_url": prov_obj.get("base_url", ""),
                            "api_key": prov_obj.get("api_key", ""),
                            "raw_model_id": matched_km.get("model_id", clean_req_model)
                        }
                        actual_model = matched_km.get("model_id", clean_req_model)
                        matched_cloud = True
            except Exception as m_err:
                print(f"⚠️ Gateway: Error validando modelo en MongoDB: {m_err}", file=sys.stderr, flush=True)

        if not matched_cloud:
            async with cached_cloud_models_lock:
                if clean_req_model in cached_cloud_models:
                    is_cloud_request = True
                    cloud_provider = cached_cloud_models[clean_req_model]
                    actual_model = cloud_provider.get("raw_model_id", clean_req_model)
                elif clean_req_model in cached_cloud_models_by_raw:
                    candidate_providers = cached_cloud_models_by_raw[clean_req_model]
                    authorized_candidate = None
                    for cp in candidate_providers:
                        p_id = cp.get("provider_id", "")
                        p_name = cp.get("provider_name", "")
                        p_slug = cp.get("provider_slug", "")
                        if is_master or ("*" in key_allowed_providers) or (p_id in key_allowed_providers) or (p_name in key_allowed_providers) or (p_slug in key_allowed_providers):
                            authorized_candidate = cp
                            break

                    if ("gemma" in allowed_services or is_master) and (clean_req_model in ["gemma-4-reasoning", "gemma-4-web", "gemma-4-rag", "google/gemma-4-E4B-it"] or not authorized_candidate):
                        is_cloud_request = False
                        actual_model = clean_req_model
                        if clean_req_model in ["gemma-4-web", "gemma-4-rag"]:
                            base_vllm_model = get_env_setting("MODEL", "google/gemma-4-E4B-it").strip('"').strip("'")
                    elif authorized_candidate:
                        is_cloud_request = True
                        cloud_provider = authorized_candidate
                        actual_model = clean_req_model
                    else:
                        is_cloud_request = True
                        cloud_provider = candidate_providers[0]
                        actual_model = clean_req_model
                else:
                    is_cloud_request = False
                    actual_model = clean_req_model

    return is_cloud_request, actual_model, cloud_provider, apply_rag_injection, base_vllm_model
