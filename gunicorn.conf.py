"""
Configuración de producción de Gunicorn para vLLM Suite Dashboard.
"""
import os

bind = f"{os.getenv('DASHBOARD_HOST', '0.0.0.0')}:{os.getenv('DASHBOARD_PORT', '8004')}"
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = "gthread"
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
proc_name = "vllm-dashboard"
accesslog = "-"
errorlog = "-"


def on_starting(server):
    """Inicializa la telemetría y TTL de base de datos antes de servir peticiones."""
    try:
        from dashboard.core import init_db_telemetry, start_telemetry_collector
        init_db_telemetry()
        start_telemetry_collector()
    except Exception as e:
        import sys
        print(f"⚠️ Error en hook on_starting de Gunicorn: {e}", file=sys.stderr)
