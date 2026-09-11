import os
import psutil
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify
from dashboard.core import (
    SERVICES,
    SERVICE_PORTS,
    get_gpu_info,
    get_cpu_temperature,
    get_service_status,
    control_service,
    parse_env_to_dict,
    save_env_from_dict
)

system_bp = Blueprint("system", __name__)

@system_bp.route("/api/status", methods=["GET"])
def api_status():
    """Devuelve las métricas de hardware del sistema (CPU, RAM, GPU, VRAM) y el estado de los servicios."""
    gpu = get_gpu_info()
    
    services_info = {}
    for key, service_name in SERVICES.items():
        services_info[key] = {
            "name": service_name,
            "status": get_service_status(service_name),
            "port": SERVICE_PORTS.get(key, "")
        }
        
    vram_percent = 0.0
    if gpu["total_vram"] > 0:
        vram_percent = round((gpu["used_vram"] / gpu["total_vram"]) * 100, 2)
        
    return jsonify({
        "system": {
            "cpu": psutil.cpu_percent(),
            "cpu_temp": get_cpu_temperature(),
            "ram": psutil.virtual_memory().percent,
            "gpu_util": gpu["gpu_util"],
            "gpu_temp": gpu["gpu_temp"],
            "vram_total": gpu["total_vram"],
            "vram_used": gpu["used_vram"],
            "vram_percent": vram_percent
        },
        "services": services_info
    })


@system_bp.route("/api/service/<service_key>/<action>", methods=["POST"])
def api_control_service(service_key, action):
    """Inicia, detiene o reinicia un servicio systemd administrado."""
    if service_key not in SERVICES:
        return jsonify({"success": False, "error": "Servicio inválido"}), 400
    if action not in ["start", "stop", "restart"]:
        return jsonify({"success": False, "error": "Acción inválida"}), 400
        
    service_name = SERVICES[service_key]
    success = control_service(service_name, action)
    
    return jsonify({
        "success": success,
        "service": service_key,
        "action": action,
        "new_status": get_service_status(service_name)
    })


@system_bp.route("/api/config", methods=["GET"])
def api_get_config():
    """Retorna las variables del archivo .env como un diccionario JSON."""
    return jsonify(parse_env_to_dict())


@system_bp.route("/api/config", methods=["POST"])
def api_save_config():
    """Actualiza el archivo .env con los nuevos valores recibidos."""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
    try:
        save_env_from_dict(data)
        load_dotenv(override=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
