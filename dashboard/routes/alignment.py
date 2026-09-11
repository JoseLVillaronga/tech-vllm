from flask import Blueprint, request, jsonify

alignment_bp = Blueprint("alignment", __name__)

@alignment_bp.route("/api/alignment/settings", methods=["GET", "POST"])
def api_alignment_settings():
    """Obtiene o actualiza las directivas y políticas de alineación MEA en MongoDB."""
    try:
        from gateway.core.alignment_engine import get_alignment_settings, save_alignment_settings
        if request.method == "POST":
            data = request.get_json() or {}
            success = save_alignment_settings(data)
            if success:
                return jsonify({"success": True, "message": "Políticas de alineación guardadas y aplicadas en caliente."})
            return jsonify({"success": False, "message": "Error al persistir en base de datos."}), 500
        else:
            settings = get_alignment_settings()
            return jsonify({"success": True, "settings": settings})
    except Exception as e:
        return jsonify({"success": False, "error": f"Error en configuración de alineación: {str(e)}"}), 500
