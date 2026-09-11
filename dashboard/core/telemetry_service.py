import sys
import time
import psutil
import threading
from datetime import datetime, timezone
from dashboard.core.database import get_db
from dashboard.core.system_metrics import (
    get_gpu_info,
    get_cpu_temperature,
    SERVICES,
    get_service_status
)


def init_db_telemetry():
    """
    Inicializa los índices TTL de MongoDB para telemetría y reglas de IP.
    """
    try:
        db = get_db()
        db.telemetry_history.create_index("timestamp", expireAfterSeconds=604800)
        print("💾 MongoDB: Índice TTL de 7 días configurado en telemetry_history.")
        
        # Crear índice TTL en ip_rules sobre expires_at para autolimpieza de baneos temporales (48h)
        db.ip_rules.create_index("expires_at", expireAfterSeconds=0)
        print("💾 MongoDB: Índice TTL dinámico configurado en ip_rules (expires_at).")
    except Exception as e:
        print(f"⚠️ Error al configurar índices de base de datos en MongoDB: {e}", file=sys.stderr)


_collector_started = False
_collector_lock = threading.Lock()


def start_telemetry_collector():
    """
    Inicia el hilo en segundo plano de recolección de telemetría periódica cada 60s.
    """
    global _collector_started
    with _collector_lock:
        if _collector_started:
            return
        _collector_started = True

    def telemetry_loop():
        # Esperar 5s de calentamiento inicial
        time.sleep(5)
        print("📊 Recolector de Telemetría Histórica Iniciado (muestreo cada 60s).")
        while True:
            try:
                # 1. Obtener info de GPU
                gpu = get_gpu_info()
                gpu_util = gpu.get("gpu_util", 0) if gpu else 0
                gpu_temp = gpu.get("gpu_temp", 0) if gpu else 0
                vram_used = gpu.get("used_vram", 0) / 1024.0 if gpu else 0  # Convertir a GB
                vram_total = gpu.get("total_vram", 0) / 1024.0 if gpu else 0
                
                # 2. Obtener info de CPU y RAM
                cpu_util = psutil.cpu_percent()
                cpu_temp = get_cpu_temperature() or 0.0
                ram = psutil.virtual_memory()
                ram_util = ram.percent
                
                # 3. Obtener estado de los servicios
                services_status = {}
                for key, svc_name in SERVICES.items():
                    services_status[key] = get_service_status(svc_name)
                    
                # 4. Registrar en MongoDB
                db = get_db()
                db.telemetry_history.insert_one({
                    "timestamp": datetime.now(timezone.utc),
                    "cpu": cpu_util,
                    "cpu_temp": cpu_temp,
                    "ram": ram_util,
                    "gpu_util": gpu_util,
                    "gpu_temp": gpu_temp,
                    "vram_used": round(vram_used, 2),
                    "vram_total": round(vram_total, 2),
                    "services": services_status
                })
            except Exception as ex:
                print(f"⚠️ Error en bucle de telemetría: {ex}", file=sys.stderr)
            time.sleep(60)

    t = threading.Thread(target=telemetry_loop, daemon=True)
    t.start()
