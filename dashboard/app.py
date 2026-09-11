import os
import sys
from flask import Flask
from dashboard.core import (
    REPO_ROOT,
    init_db_telemetry,
    start_telemetry_collector
)
from dashboard.routes import ALL_BLUEPRINTS

PORT = int(os.getenv("DASHBOARD_PORT", "8004"))


def create_app():
    """Fábrica de aplicación Flask para el Dashboard de Administración."""
    application = Flask(
        __name__,
        static_folder=str(REPO_ROOT / "static"),
        template_folder=str(REPO_ROOT / "templates")
    )

    # Registrar todos los Blueprints modulares
    for bp in ALL_BLUEPRINTS:
        application.register_blueprint(bp)

    return application


app = create_app()


def _run_with_gunicorn(application, host: str, port: int):
    """Ejecuta la aplicación bajo el servidor WSGI de producción Gunicorn con pool gthread."""
    from gunicorn.app.base import BaseApplication

    class StandaloneGunicornApp(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None:
                    self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    workers = int(os.getenv("GUNICORN_WORKERS", "1"))
    threads = int(os.getenv("GUNICORN_THREADS", "4"))
    timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))

    options = {
        "bind": f"{host}:{port}",
        "workers": workers,
        "threads": threads,
        "worker_class": "gthread",
        "timeout": timeout,
        "accesslog": "-",
        "errorlog": "-",
        "proc_name": "vllm-dashboard",
    }
    StandaloneGunicornApp(application, options).run()


def main():
    """Punto de entrada principal para el servicio del Dashboard."""
    init_db_telemetry()
    start_telemetry_collector()

    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    try:
        _run_with_gunicorn(app, host=host, port=PORT)
    except ImportError:
        print("⚠️ Gunicorn no está disponible, usando servidor Werkzeug.", file=sys.stderr)
        app.run(host=host, port=PORT)


if __name__ == "__main__":
    main()
