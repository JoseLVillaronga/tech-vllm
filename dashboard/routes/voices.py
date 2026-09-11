import os
import uuid
from bson import ObjectId
from flask import Blueprint, request, jsonify
from dashboard.core import get_db, resample_audio_to_24k_mono, REPO_ROOT

voices_bp = Blueprint("voices", __name__)

@voices_bp.route("/api/voices", methods=["GET"])
def api_get_voices():
    """Obtiene la lista de perfiles y voces clonadas registradas en la base de datos."""
    try:
        db = get_db()
        voices = list(db.reference_voices.find())
        result = []
        for v in voices:
            audio_path = v.get("audio_path", "")
            audio_url = (audio_path[audio_path.find("/static/"):] if "/static/" in audio_path else audio_path)
            result.append({
                "id": str(v["_id"]),
                "name": v.get("name", "Sin nombre"),
                "description": v.get("description", ""),
                "text": v.get("text", ""),
                "audio_path": audio_path,
                "audio_url": audio_url,
                "is_active": v.get("is_active", False)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@voices_bp.route("/api/voices", methods=["POST"])
def api_create_voice():
    """Sube una muestra de audio, la re-muestrea a 24kHz mono y registra un perfil de voz clonado."""
    try:
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        text = request.form.get("text", "").strip()
        
        if not name or not text:
            return jsonify({"error": "El nombre y el texto de referencia son obligatorios"}), 400
            
        if "file" not in request.files:
            return jsonify({"error": "El archivo de audio es obligatorio"}), 400
            
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No se seleccionó ningún archivo"}), 400
            
        upload_dir = str(REPO_ROOT / "static" / "audio" / "clones")
        os.makedirs(upload_dir, exist_ok=True)
        
        temp_ext = os.path.splitext(file.filename)[1] or ".wav"
        temp_filename = f"temp_{uuid.uuid4().hex}{temp_ext}"
        temp_path = os.path.join(upload_dir, temp_filename)
        file.save(temp_path)
        
        final_filename = f"voice_{uuid.uuid4().hex}.wav"
        final_path = os.path.join(upload_dir, final_filename)
        
        success = resample_audio_to_24k_mono(temp_path, final_path)
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if not success:
            return jsonify({"error": "Error al procesar y re-muestrear el archivo de audio"}), 500
            
        db = get_db()
        has_voices = db.reference_voices.count_documents({}) > 0
        is_active = not has_voices  # Activa si es la primera
        
        if is_active:
            db.reference_voices.update_many({}, {"$set": {"is_active": False}})
            
        voice_id = db.reference_voices.insert_one({
            "name": name,
            "description": description,
            "text": text,
            "audio_path": final_path,
            "is_active": is_active
        }).inserted_id
        
        return jsonify({
            "message": "Perfil de voz creado con éxito",
            "id": str(voice_id),
            "is_active": is_active
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@voices_bp.route("/api/voices/<voice_id>", methods=["PUT"])
def api_update_voice(voice_id):
    """Actualiza metadatos de un perfil de voz."""
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        text = data.get("text", "").strip()
        
        if not name or not text:
            return jsonify({"error": "El nombre y el texto de referencia son obligatorios"}), 400
            
        db = get_db()
        res = db.reference_voices.update_one(
            {"_id": ObjectId(voice_id)},
            {"$set": {
                "name": name,
                "description": description,
                "text": text
            }}
        )
        
        if res.matched_count == 0:
            return jsonify({"error": "Perfil de voz no encontrado"}), 404
            
        return jsonify({"message": "Perfil de voz actualizado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@voices_bp.route("/api/voices/<voice_id>/activate", methods=["POST"])
def api_activate_voice(voice_id):
    """Activa una voz para su uso predeterminado en el motor TTS."""
    try:
        db = get_db()
        voice = db.reference_voices.find_one({"_id": ObjectId(voice_id)})
        if not voice:
            return jsonify({"error": "Perfil de voz no encontrado"}), 404
            
        db.reference_voices.update_many({}, {"$set": {"is_active": False}})
        db.reference_voices.update_one({"_id": ObjectId(voice_id)}, {"$set": {"is_active": True}})
        
        return jsonify({"message": f"Perfil '{voice['name']}' activado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@voices_bp.route("/api/voices/<voice_id>", methods=["DELETE"])
def api_delete_voice(voice_id):
    """Elimina un perfil de voz y borra su archivo de audio asociado del disco."""
    try:
        db = get_db()
        voice = db.reference_voices.find_one({"_id": ObjectId(voice_id)})
        if not voice:
            return jsonify({"error": "Perfil de voz no encontrado"}), 404
            
        audio_path = voice.get("audio_path", "")
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                print(f"Error borrando archivo de audio {audio_path}: {e}")
                
        db.reference_voices.delete_one({"_id": ObjectId(voice_id)})
        
        if voice.get("is_active", False):
            first_remaining = db.reference_voices.find_one()
            if first_remaining:
                db.reference_voices.update_one(
                    {"_id": first_remaining["_id"]},
                    {"$set": {"is_active": True}}
                )
                
        return jsonify({"message": "Perfil de voz eliminado con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
