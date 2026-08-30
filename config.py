"""
config.py — Fuente única de configuración de entorno para la vLLM Local Suite.

Carga el archivo .env ubicado junto a este módulo (robusto ante cambios del
directorio de trabajo, p. ej. servicios systemd con WorkingDirectory distinto)
y expone las variables de entorno usadas por los distintos servicios.

Objetivo de seguridad: eliminar credenciales hardcodeadas del código fuente.
Todos los servicios leen aquí las variables reales desde el entorno o desde
.env; si una variable sensible no está definida, su valor queda vacío (fail
closed) en lugar de caer en una clave por defecto conocida.
"""
import os

from dotenv import load_dotenv

# Ruta absoluta al .env junto a este archivo (no depende del CWD del proceso).
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH)


def env(key: str, default: str = "") -> str:
    """Lee una variable de entorno recortando espacios.

    Si la variable no existe o está vacía, devuelve ``default``. Para usuarios
    de secretos el default por defecto es ``""``, de modo que un servicio nunca
    arranca con una credencial conocida e incrustada.
    """
    val = os.getenv(key)
    if val is None:
        return default
    val = val.strip()
    return val if val != "" else default


# --------------------------------------------------------------------------- #
# Credenciales y configuración global
# --------------------------------------------------------------------------- #
API_KEY = env("API_KEY")                  # Sin fallback con frase conocida (seguridad)

MONGO_USER = env("MONGO_USER", "admin")
MONGO_PASS = env("MONGO_PASS")            # Sin fallback real hardcodeado
MONGO_HOST = env("MONGO_HOST", "127.0.0.1")
MONGO_DB = env("MONGO_DB", "vllm")


def get_mongo_uri(db_name: str = None, auth_source: str = "admin", port: int = 27017) -> str:
    """Construye la URI de conexión a MongoDB sin exponer credenciales hardcodeadas.

    Si ``MONGO_PASS`` está vacío, la URI se genera sin credenciales (usuario sin
    clave), que es el comportamiento correcto para una instancia local sin auth.
    """
    db = db_name or MONGO_DB
    cred = f"{MONGO_USER}:{MONGO_PASS}" if MONGO_PASS else MONGO_USER
    return f"mongodb://{cred}@{MONGO_HOST}:{port}/{db}?authSource={auth_source}"
