"""
Registro central de Blueprints de la API y Frontend del Dashboard.
"""

from .frontend import frontend_bp
from .system import system_bp
from .keys import keys_bp
from .telemetry import telemetry_bp
from .security import security_bp
from .cloud import cloud_bp
from .voices import voices_bp
from .rag import rag_bp
from .alignment import alignment_bp
from .tests import tests_bp
from .auth import auth_bp
from .users import users_bp

ALL_BLUEPRINTS = [
    auth_bp,
    users_bp,
    frontend_bp,
    system_bp,
    keys_bp,
    telemetry_bp,
    security_bp,
    cloud_bp,
    voices_bp,
    rag_bp,
    alignment_bp,
    tests_bp,
]

__all__ = [
    "auth_bp",
    "users_bp",
    "frontend_bp",
    "system_bp",
    "keys_bp",
    "telemetry_bp",
    "security_bp",
    "cloud_bp",
    "voices_bp",
    "rag_bp",
    "alignment_bp",
    "tests_bp",
    "ALL_BLUEPRINTS"
]
