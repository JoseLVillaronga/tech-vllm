"""
Paquete vLLM Suite Gateway (Modular Architecture).
Provee reverse proxy, seguridad, RBAC, herramientas desacopladas y telemetría.
Garantiza la carga unificada de variables de entorno desde .env.
"""
import os
from dotenv import load_dotenv

# Cargar de forma determinista el archivo .env ubicado en la raíz del proyecto
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(_ROOT_DIR, ".env")
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH)

__version__ = "2.0.0"
