import sys
import secrets
from datetime import datetime, timezone
from bson import ObjectId
from flask import Blueprint, request, jsonify
from dashboard.core import get_db, check_and_reset_key_quota_dict, slugify_provider_name

keys_bp = Blueprint("keys", __name__)

@keys_bp.route("/api/keys", methods=["GET"])
def api_get_keys():
    """Retorna la lista de todas las claves API registradas con sus cuotas y modelos asociados."""
    try:
        db = get_db()
        keys = list(db.api_keys.find())
        result = []
        for k in keys:
            k = check_and_reset_key_quota_dict(k, db)
            key_id = k["_id"]
            # Obtener modelos asignados para esta clave
            key_models = list(db.api_key_models.find({"key_id": key_id}))
            models_by_provider = {}
            for km in key_models:
                p_id = str(km.get("provider_id", ""))
                if p_id:
                    if p_id not in models_by_provider:
                        models_by_provider[p_id] = []
                    models_by_provider[p_id].append(km.get("model_id"))
            
            result.append({
                "id": str(key_id),
                "name": k.get("name", "Sin nombre"),
                "description": k.get("description", ""),
                "key": k.get("key", ""),
                "services": k.get("services", []),
                "allowed_providers": k.get("allowed_providers", []),
                "allowed_models_count": len(key_models),
                "models_by_provider": models_by_provider,
                "max_tokens": int(k.get("max_tokens") or 0),
                "used_tokens": int(k.get("used_tokens") or 0),
                "quota_reset": k.get("quota_reset", "none"),
                "last_reset_at": str(k.get("last_reset_at") or ""),
                "expires_at": k.get("expires_at", ""),
                "is_active": k.get("is_active", True),
                "company_profile": k.get("company_profile", {})
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@keys_bp.route("/api/keys/<key_id>/models", methods=["GET"])
def api_get_key_models(key_id):
    """Lista los modelos autorizados específicamente para una clave API."""
    try:
        db = get_db()
        key_models = list(db.api_key_models.find({"key_id": ObjectId(key_id)}))
        result = []
        for km in key_models:
            result.append({
                "id": str(km["_id"]),
                "key_id": str(km.get("key_id", "")),
                "provider_id": str(km.get("provider_id", "")),
                "provider_name": km.get("provider_name", ""),
                "provider_slug": km.get("provider_slug", ""),
                "model_id": km.get("model_id", ""),
                "prefixed_id": km.get("prefixed_id", "")
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@keys_bp.route("/api/keys", methods=["POST"])
def api_create_key():
    """Genera y registra una nueva clave de acceso con límites de tokens y servicios autorizados."""
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        services = data.get("services", [])
        allowed_providers = data.get("allowed_providers", [])
        allowed_models = data.get("allowed_models", {})  # Dict { "<provider_id>": ["m1", "m2"] }
        max_tokens = int(data.get("max_tokens") or 0)
        quota_reset = data.get("quota_reset", "none")
        if quota_reset not in ["none", "daily", "monthly"]:
            quota_reset = "none"
        expires_at = data.get("expires_at", "").strip()
        company_profile = data.get("company_profile", {})
        if not isinstance(company_profile, dict):
            company_profile = {}
        
        if not name:
            return jsonify({"error": "El nombre es obligatorio"}), 400
            
        if not services and not allowed_providers:
            return jsonify({"error": "Debes seleccionar al menos un servicio local o un proveedor en la nube"}), 400
            
        new_key = "vllm_key_" + secrets.token_hex(20)
        
        expires_val = None
        if expires_at:
            expires_val = expires_at
                
        db = get_db()
        key_id = db.api_keys.insert_one({
            "name": name,
            "description": description,
            "key": new_key,
            "services": services,
            "allowed_providers": allowed_providers,
            "max_tokens": max_tokens,
            "used_tokens": 0,
            "quota_reset": quota_reset,
            "last_reset_at": datetime.now(timezone.utc),
            "expires_at": expires_val,
            "is_active": True,
            "company_profile": company_profile
        }).inserted_id
        
        # Persistir modelos granulares seleccionados en db.api_key_models
        if allowed_models and isinstance(allowed_models, dict):
            docs_to_insert = []
            for p_id, m_list in allowed_models.items():
                if not m_list:
                    continue
                try:
                    p_obj = db.cloud_providers.find_one({"_id": ObjectId(p_id)})
                    if p_obj:
                        p_name = p_obj.get("name", "")
                        p_slug = slugify_provider_name(p_name)
                        for m_id in m_list:
                            docs_to_insert.append({
                                "key_id": key_id,
                                "provider_id": ObjectId(p_id),
                                "provider_name": p_name,
                                "provider_slug": p_slug,
                                "model_id": m_id,
                                "prefixed_id": f"{p_slug}/{m_id}",
                                "created_at": datetime.now(timezone.utc)
                            })
                except Exception as p_err:
                    print(f"Error procesando modelos para clave {key_id}: {p_err}", file=sys.stderr, flush=True)
            if docs_to_insert:
                db.api_key_models.insert_many(docs_to_insert)
        
        return jsonify({
            "message": "Clave API creada con éxito",
            "id": str(key_id),
            "key": new_key
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@keys_bp.route("/api/keys/<key_id>", methods=["PUT"])
def api_update_key(key_id):
    """Actualiza los permisos, modelos permitidos, vigencia o cuotas de una clave API."""
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        services = data.get("services", [])
        allowed_providers = data.get("allowed_providers", [])
        allowed_models = data.get("allowed_models", None)  # Dict { "<provider_id>": ["m1", "m2"] }
        max_tokens = int(data.get("max_tokens") or 0)
        quota_reset = data.get("quota_reset", "none")
        if quota_reset not in ["none", "daily", "monthly"]:
            quota_reset = "none"
        expires_at = data.get("expires_at", "").strip()
        is_active = data.get("is_active", True)
        company_profile = data.get("company_profile", None)
        if company_profile is not None and not isinstance(company_profile, dict):
            company_profile = {}
        
        if not name:
            return jsonify({"error": "El nombre es obligatorio"}), 400
            
        if not services and not allowed_providers:
            return jsonify({"error": "Debes seleccionar al menos un servicio local o un proveedor en la nube"}), 400
            
        expires_val = None
        if expires_at:
            expires_val = expires_at
            
        update_fields = {
            "name": name,
            "description": description,
            "services": services,
            "allowed_providers": allowed_providers,
            "max_tokens": max_tokens,
            "quota_reset": quota_reset,
            "expires_at": expires_val,
            "is_active": is_active
        }
        if company_profile is not None:
            update_fields["company_profile"] = company_profile

        db = get_db()
        res = db.api_keys.update_one(
            {"_id": ObjectId(key_id)},
            {"$set": update_fields}
        )
        
        if res.matched_count == 0:
            return jsonify({"error": "Clave API no encontrada"}), 404
            
        # Actualizar modelos granulares si se enviaron
        if allowed_models is not None and isinstance(allowed_models, dict):
            db.api_key_models.delete_many({"key_id": ObjectId(key_id)})
            docs_to_insert = []
            for p_id, m_list in allowed_models.items():
                if not m_list:
                    continue
                try:
                    p_obj = db.cloud_providers.find_one({"_id": ObjectId(p_id)})
                    if p_obj:
                        p_name = p_obj.get("name", "")
                        p_slug = slugify_provider_name(p_name)
                        for m_id in m_list:
                            docs_to_insert.append({
                                "key_id": ObjectId(key_id),
                                "provider_id": ObjectId(p_id),
                                "provider_name": p_name,
                                "provider_slug": p_slug,
                                "model_id": m_id,
                                "prefixed_id": f"{p_slug}/{m_id}",
                                "created_at": datetime.now(timezone.utc)
                            })
                except Exception as p_err:
                    print(f"Error actualizando modelos para clave {key_id}: {p_err}", file=sys.stderr, flush=True)
            if docs_to_insert:
                db.api_key_models.insert_many(docs_to_insert)
            
        return jsonify({"message": "Clave API actualizada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@keys_bp.route("/api/keys/<key_id>/reset-quota", methods=["POST"])
def api_reset_key_quota(key_id):
    """Reinicia manualmente a cero el contador de tokens consumidos de una clave API."""
    try:
        db = get_db()
        now = datetime.now(timezone.utc)
        res = db.api_keys.update_one(
            {"_id": ObjectId(key_id)},
            {"$set": {"used_tokens": 0, "last_reset_at": now}}
        )
        if res.matched_count == 0:
            return jsonify({"error": "Clave API no encontrada"}), 404
            
        return jsonify({"message": "Cupo de tokens reiniciado a cero con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@keys_bp.route("/api/keys/<key_id>", methods=["DELETE"])
def api_delete_key(key_id):
    """Elimina una clave API y revoca sus permisos asociados en el gateway."""
    try:
        db = get_db()
        db.api_key_models.delete_many({"key_id": ObjectId(key_id)})
        res = db.api_keys.delete_one({"_id": ObjectId(key_id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Clave API no encontrada"}), 404
            
        return jsonify({"message": "Clave API eliminada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
