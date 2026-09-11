from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response
from dashboard.core import get_db

telemetry_bp = Blueprint("telemetry", __name__)

@telemetry_bp.route("/api/telemetry/history", methods=["GET"])
def api_telemetry_history():
    """Retorna el historial de telemetría de hardware (CPU, RAM, GPU, VRAM) para series temporales."""
    try:
        hours = request.args.get("hours", default=6, type=int)
        start_date = datetime.utcnow() - timedelta(hours=hours)
        
        db = get_db()
        records = list(db.telemetry_history.find(
            {"timestamp": {"$gte": start_date}}
        ).sort("timestamp", 1))
        
        result = []
        for r in records:
            ts_str = r["timestamp"].isoformat() + "Z" if isinstance(r["timestamp"], datetime) else r["timestamp"]
            result.append({
                "timestamp": ts_str,
                "cpu": r.get("cpu", 0),
                "cpu_temp": r.get("cpu_temp", 0),
                "ram": r.get("ram", 0),
                "gpu_util": r.get("gpu_util", 0),
                "gpu_temp": r.get("gpu_temp", 0),
                "vram_used": r.get("vram_used", 0),
                "vram_total": r.get("vram_total", 0),
                "services": r.get("services", {})
            })
            
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@telemetry_bp.route("/api/metrics", methods=["GET"])
def api_metrics():
    """Calcula y agrupa métricas de uso de API (llamadas, tokens, tiempos de cómputo, distribución por modelo)."""
    try:
        days = request.args.get("days", default=7, type=int)
        service = request.args.get("service", default="", type=str)
        api_key = request.args.get("api_key", default="", type=str)
        model = request.args.get("model", default="", type=str)
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = {"timestamp": {"$gte": start_date}}
        if service:
            query["service"] = service
        if api_key:
            query["api_key_name"] = api_key
        if model:
            query["model"] = model
            
        db = get_db()
        logs = list(db.usage_logs.find(query).sort("timestamp", 1))
        
        time_series = {}
        service_shares = {}
        api_key_shares = {}
        model_shares = {}
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_audio_sec = 0.0
        total_calls = len(logs)
        
        for i in range(days):
            day_str = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            time_series[day_str] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "audio_duration_sec": 0.0,
                "calls": 0
            }
            
        for log in logs:
            ts = log["timestamp"]
            day_str = ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else ts[:10]
            
            p_tokens = log.get("prompt_tokens", 0)
            c_tokens = log.get("completion_tokens", 0)
            a_sec = log.get("audio_duration_sec", 0.0)
            
            total_prompt_tokens += p_tokens
            total_completion_tokens += c_tokens
            total_audio_sec += a_sec
            
            if day_str in time_series:
                time_series[day_str]["prompt_tokens"] += p_tokens
                time_series[day_str]["completion_tokens"] += c_tokens
                time_series[day_str]["audio_duration_sec"] += a_sec
                time_series[day_str]["calls"] += 1
                
            srv = log.get("service", "unknown")
            service_shares[srv] = service_shares.get(srv, 0) + 1
            
            key = log.get("api_key_name", "unknown")
            api_key_shares[key] = api_key_shares.get(key, 0) + 1
            
            mdl = log.get("model", "unknown")
            model_shares[mdl] = model_shares.get(mdl, 0) + 1
            
        sorted_time_series = [
            {"date": date, **metrics}
            for date, metrics in sorted(time_series.items())
        ]
        
        api_keys_list = list(db.api_keys.find({}, {"name": 1}))
        api_key_names = ["Master Key"] + [k["name"] for k in api_keys_list if k.get("name")]
        unique_models = db.usage_logs.distinct("model")
        
        return jsonify({
            "summary": {
                "total_calls": total_calls,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_audio_sec": round(total_audio_sec, 2),
            },
            "time_series": sorted_time_series,
            "shares": {
                "service": service_shares,
                "api_key": api_key_shares,
                "model": model_shares
            },
            "filters_data": {
                "api_keys": api_key_names,
                "models": unique_models
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@telemetry_bp.route("/api/metrics/export", methods=["GET"])
def api_export_metrics():
    """Exporta los logs de consumo a formato CSV descargable."""
    try:
        days = request.args.get("days", default=7, type=int)
        service = request.args.get("service", default="", type=str)
        api_key = request.args.get("api_key", default="", type=str)
        model = request.args.get("model", default="", type=str)
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = {"timestamp": {"$gte": start_date}}
        if service:
            query["service"] = service
        if api_key:
            query["api_key_name"] = api_key
        if model:
            query["model"] = model
            
        db = get_db()
        logs = list(db.usage_logs.find(query).sort("timestamp", -1))
        
        def generate():
            yield "\ufeff"
            headers = [
                "Fecha y Hora",
                "IP Cliente",
                "Clave API",
                "Servicio",
                "Endpoint",
                "Modelo",
                "Tokens Entrada",
                "Tokens Salida",
                "Duracion Audio (seg)",
                "Tiempo Procesamiento (seg)"
            ]
            yield ";".join(headers) + "\n"
            
            for log in logs:
                ts = log.get("timestamp")
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, datetime) else str(ts)
                
                row = [
                    ts_str,
                    log.get("ip") or log.get("client_ip", ""),
                    log.get("api_key_name", ""),
                    log.get("service", ""),
                    log.get("endpoint") or log.get("path", ""),
                    log.get("model", ""),
                    str(log.get("prompt_tokens", 0)),
                    str(log.get("completion_tokens", 0)),
                    f"{log.get('audio_duration_sec', 0.0):.2f}",
                    f"{log.get('duration_sec', 0.0):.2f}"
                ]
                row_cleaned = [str(val).replace(";", " ").replace("\n", " ").replace("\r", " ") for val in row]
                yield ";".join(row_cleaned) + "\n"
                
        return Response(
            generate(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=telemetria_consumo.csv"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
