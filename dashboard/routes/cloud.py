import requests
from bson import ObjectId
from flask import Blueprint, request, jsonify
from dashboard.core import get_db, slugify_provider_name

cloud_bp = Blueprint("cloud", __name__)

@cloud_bp.route("/api/cloud-providers", methods=["GET"])
def api_get_cloud_providers():
    """Lista los proveedores de nube OpenAI-compatibles registrados en la plataforma."""
    try:
        db = get_db()
        providers = list(db.cloud_providers.find())
        result = []
        for p in providers:
            key = p.get("api_key", "")
            masked_key = key[:8] + "..." if len(key) > 8 else "..."
            result.append({
                "id": str(p["_id"]),
                "name": p.get("name", ""),
                "base_url": p.get("base_url", ""),
                "api_key": masked_key,
                "is_active": p.get("is_active", True)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cloud_bp.route("/api/cloud-providers", methods=["POST"])
def api_create_cloud_provider():
    """Registra un nuevo proveedor en la nube con su clave API y URL base."""
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        base_url = data.get("base_url", "").strip()
        api_key = data.get("api_key", "").strip()
        is_active = data.get("is_active", True)
        
        if not name or not base_url or not api_key:
            return jsonify({"error": "Todos los campos son requeridos"}), 400
            
        db = get_db()
        db.cloud_providers.insert_one({
            "name": name,
            "base_url": base_url,
            "api_key": api_key,
            "is_active": is_active
        })
        return jsonify({"message": "Proveedor en la nube creado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cloud_bp.route("/api/cloud-providers/<provider_id>", methods=["PUT"])
def api_update_cloud_provider(provider_id):
    """Actualiza la configuración o clave API de un proveedor cloud."""
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        base_url = data.get("base_url", "").strip()
        api_key = data.get("api_key", "").strip()
        is_active = data.get("is_active", True)
        
        update_doc = {
            "name": name,
            "base_url": base_url,
            "is_active": is_active
        }
        if api_key and not api_key.endswith("..."):
            update_doc["api_key"] = api_key
            
        db = get_db()
        res = db.cloud_providers.update_one(
            {"_id": ObjectId(provider_id)},
            {"$set": update_doc}
        )
        if res.matched_count == 0:
            return jsonify({"error": "Proveedor no encontrado"}), 404
            
        return jsonify({"message": "Proveedor en la nube actualizado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cloud_bp.route("/api/cloud-providers/<provider_id>/models", methods=["GET"])
def api_get_cloud_provider_models(provider_id):
    """Consulta en vivo el catálogo de modelos disponibles en el endpoint /models del proveedor."""
    try:
        db = get_db()
        provider = db.cloud_providers.find_one({"_id": ObjectId(provider_id)})
        if not provider:
            return jsonify({"error": "Proveedor no encontrado"}), 404
        
        base_url = provider.get("base_url", "").rstrip("/")
        api_key = provider.get("api_key", "")
        if not base_url or not api_key:
            return jsonify({"error": "El proveedor no tiene configurada base_url o api_key"}), 400
        
        headers = {"Authorization": f"Bearer {api_key}"}
        models_url = f"{base_url}/models" if not base_url.endswith("/models") else base_url
        try:
            resp = requests.get(models_url, headers=headers, timeout=7.0)
        except Exception as net_err:
            return jsonify({"error": f"No se pudo conectar con el proveedor: {net_err}"}), 502
            
        if resp.status_code != 200:
            return jsonify({"error": f"El proveedor devolvió código HTTP {resp.status_code}: {resp.text[:200]}"}), 502
            
        models_data = resp.json()
        raw_list = models_data.get("data", [])
        formatted_models = []
        slug = slugify_provider_name(provider.get("name", "cloud"))
        for m in raw_list:
            m_id = m.get("id")
            if m_id:
                formatted_models.append({
                    "id": m_id,
                    "prefixed_id": f"{slug}/{m_id}",
                    "name": m.get("name") or m_id,
                    "created": m.get("created"),
                    "owned_by": m.get("owned_by") or provider.get("name", "cloud")
                })
        return jsonify({
            "provider_id": provider_id,
            "provider_name": provider.get("name", ""),
            "provider_slug": slug,
            "models": formatted_models
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cloud_bp.route("/api/cloud-providers/<provider_id>", methods=["DELETE"])
def api_delete_cloud_provider(provider_id):
    """Elimina un proveedor cloud y desvincula sus modelos asignados a claves API."""
    try:
        db = get_db()
        db.api_key_models.delete_many({"provider_id": ObjectId(provider_id)})
        res = db.cloud_providers.delete_one({"_id": ObjectId(provider_id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Proveedor no encontrado"}), 404
            
        return jsonify({"message": "Proveedor en la nube eliminado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
