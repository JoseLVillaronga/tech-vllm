import re
import io
import csv
import ipaddress
from datetime import datetime, timedelta
from bson import ObjectId
from flask import Blueprint, request, jsonify, make_response
from dashboard.core import get_db

security_bp = Blueprint("security", __name__)

@security_bp.route("/api/ip-rules", methods=["GET"])
def api_get_ip_rules():
    """Lista las reglas de filtrado IP (whitelist / blacklist) en formato CIDR."""
    try:
        db = get_db()
        rules = list(db.ip_rules.find())
        result = []
        for r in rules:
            result.append({
                "id": str(r["_id"]),
                "name": r.get("name", "Sin nombre"),
                "network": r.get("network", ""),
                "action": r.get("action", "whitelist"),
                "is_active": r.get("is_active", True)
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@security_bp.route("/api/blocked-requests", methods=["GET"])
def api_get_blocked_requests():
    """Consulta paginada y filtrada del registro de solicitudes bloqueadas por seguridad o falta de cupo."""
    try:
        page = request.args.get("page", default=1, type=int)
        limit = request.args.get("limit", default=10, type=int)
        if page < 1:
            page = 1
        if limit < 1:
            limit = 10
            
        start_date_str = request.args.get("start_date", default="", type=str)
        end_date_str = request.args.get("end_date", default="", type=str)
        ip = request.args.get("ip", default="", type=str)
        service = request.args.get("service", default="", type=str)
        endpoint = request.args.get("endpoint", default="", type=str)
        reason = request.args.get("reason", default="", type=str)
        
        query = {}
        
        if start_date_str or end_date_str:
            time_filter = {}
            if start_date_str:
                try:
                    start_dt = datetime.fromisoformat(start_date_str)
                    time_filter["$gte"] = start_dt
                except Exception:
                    pass
            if end_date_str:
                try:
                    end_dt = datetime.fromisoformat(end_date_str) + timedelta(days=1) - timedelta(milliseconds=1)
                    time_filter["$lte"] = end_dt
                except Exception:
                    pass
            if time_filter:
                query["timestamp"] = time_filter
        else:
            hours = request.args.get("hours", default=24, type=int)
            start_date = datetime.utcnow() - timedelta(hours=hours)
            query["timestamp"] = {"$gte": start_date}
            
        if ip:
            query["ip"] = {"$regex": re.escape(ip), "$options": "i"}
        if service:
            query["service"] = service
        if endpoint:
            query["endpoint"] = {"$regex": re.escape(endpoint), "$options": "i"}
        if reason:
            query["reason"] = reason
            
        db = get_db()
        
        total_records = db.blocked_requests.count_documents(query)
        total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
        
        skip = (page - 1) * limit
        logs = list(db.blocked_requests.find(query).sort("timestamp", -1).skip(skip).limit(limit))
        
        result = []
        for l in logs:
            ts_str = l["timestamp"].isoformat() + "Z" if isinstance(l["timestamp"], datetime) else l["timestamp"]
            result.append({
                "id": str(l["_id"]),
                "timestamp": ts_str,
                "ip": l.get("ip", ""),
                "service": l.get("service", ""),
                "endpoint": l.get("endpoint", ""),
                "reason": l.get("reason", "")
            })
            
        return jsonify({
            "logs": result,
            "total_records": total_records,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@security_bp.route("/api/blocked-requests/export", methods=["GET"])
def api_export_blocked_requests():
    """Exporta los eventos de bloqueo a un archivo CSV."""
    try:
        start_date_str = request.args.get("start_date", default="", type=str)
        end_date_str = request.args.get("end_date", default="", type=str)
        ip = request.args.get("ip", default="", type=str)
        service = request.args.get("service", default="", type=str)
        endpoint = request.args.get("endpoint", default="", type=str)
        reason = request.args.get("reason", default="", type=str)
        
        query = {}
        if start_date_str or end_date_str:
            time_filter = {}
            if start_date_str:
                try:
                    start_dt = datetime.fromisoformat(start_date_str)
                    time_filter["$gte"] = start_dt
                except Exception:
                    pass
            if end_date_str:
                try:
                    end_dt = datetime.fromisoformat(end_date_str) + timedelta(days=1) - timedelta(milliseconds=1)
                    time_filter["$lte"] = end_dt
                except Exception:
                    pass
            if time_filter:
                query["timestamp"] = time_filter
        else:
            hours = request.args.get("hours", default=24, type=int)
            start_date = datetime.utcnow() - timedelta(hours=hours)
            query["timestamp"] = {"$gte": start_date}
            
        if ip:
            query["ip"] = {"$regex": re.escape(ip), "$options": "i"}
        if service:
            query["service"] = service
        if endpoint:
            query["endpoint"] = {"$regex": re.escape(endpoint), "$options": "i"}
        if reason:
            query["reason"] = reason
            
        db = get_db()
        logs = list(db.blocked_requests.find(query).sort("timestamp", -1))
        
        si = io.StringIO()
        si.write('\ufeff')
        cw = csv.writer(si, delimiter=';')
        
        cw.writerow(["Fecha y Hora (UTC)", "Dirección IP", "Servicio", "Ruta (Endpoint)", "Motivo / Filtro"])
        
        for l in logs:
            ts = l["timestamp"]
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts)
            cw.writerow([
                ts_str,
                l.get("ip", ""),
                l.get("service", ""),
                l.get("endpoint", ""),
                "LISTA BLANCA" if l.get("reason") == "whitelist" else ("CLAVE API ERROR" if l.get("reason") == "api_key" else "LISTA NEGRA")
            ])
            
        response = make_response(si.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=bloqueos_seguridad.csv"
        response.headers["Content-type"] = "text/csv; charset=utf-8"
        return response
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@security_bp.route("/api/ip-rules", methods=["POST"])
def api_create_ip_rule():
    """Crea una nueva regla CIDR de lista blanca o negra."""
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        network_str = data.get("network", "").strip()
        action = data.get("action", "whitelist").lower()
        is_active = data.get("is_active", True)
        
        if not name or not network_str:
            return jsonify({"error": "Nombre y Red/IP son requeridos"}), 400
            
        if action not in ["whitelist", "blacklist"]:
            return jsonify({"error": "Acción inválida. Debe ser whitelist o blacklist"}), 400
            
        try:
            ipaddress.ip_network(network_str, strict=False)
        except ValueError as val_err:
            return jsonify({"error": f"Sintaxis de Red/IP inválida: {val_err}"}), 400
            
        db = get_db()
        existing = db.ip_rules.find_one({"network": network_str})
        if existing:
            return jsonify({"error": f"La IP o rango '{network_str}' ya existe registrado."}), 400
            
        rule = {
            "name": name,
            "network": network_str,
            "action": action,
            "is_active": is_active
        }
        res = db.ip_rules.insert_one(rule)
        return jsonify({"message": "Regla de IP creada con éxito", "id": str(res.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@security_bp.route("/api/ip-rules/<rule_id>", methods=["PUT"])
def api_update_ip_rule(rule_id):
    """Actualiza una regla CIDR existente."""
    try:
        data = request.json or {}
        name = data.get("name", "").strip()
        network_str = data.get("network", "").strip()
        action = data.get("action", "whitelist").lower()
        is_active = data.get("is_active", True)
        
        if not name or not network_str:
            return jsonify({"error": "Nombre y Red/IP son requeridos"}), 400
            
        if action not in ["whitelist", "blacklist"]:
            return jsonify({"error": "Acción inválida"}), 400
            
        try:
            ipaddress.ip_network(network_str, strict=False)
        except ValueError as val_err:
            return jsonify({"error": f"Sintaxis de Red/IP inválida: {val_err}"}), 400
            
        db = get_db()
        res = db.ip_rules.update_one(
            {"_id": ObjectId(rule_id)},
            {"$set": {
                "name": name,
                "network": network_str,
                "action": action,
                "is_active": is_active
            }}
        )
        if res.matched_count == 0:
            return jsonify({"error": "Regla de IP no encontrada"}), 404
            
        return jsonify({"message": "Regla de IP actualizada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@security_bp.route("/api/ip-rules/<rule_id>", methods=["DELETE"])
def api_delete_ip_rule(rule_id):
    """Elimina una regla CIDR de filtrado IP."""
    try:
        db = get_db()
        res = db.ip_rules.delete_one({"_id": ObjectId(rule_id)})
        if res.deleted_count == 0:
            return jsonify({"error": "Regla de IP no encontrada"}), 404
            
        return jsonify({"message": "Regla de IP eliminada con éxito"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
