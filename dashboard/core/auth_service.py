"""
auth_service.py - Núcleo de autenticación, resolución de IP y gestión de usuarios.

Aplica las directivas de seguridad para el Dashboard de vLLM Suite:
1. El usuario 'admin' es la cuenta maestra y ÚNICAMENTE puede autenticarse
   si la conexión proviene estrictamente de localhost (127.0.0.1 o ::1).
   Su contraseña se obtiene en tiempo real de ADMIN_PASS (.env).
2. Los usuarios remotos se almacenan en MongoDB (db.dashboard_users) con
   contraseñas encriptadas mediante hashes criptográficos con salt (scrypt/pbkdf2).
3. Resolución segura de IP anti-suplantación (anti-spoofing) evaluando
   X-Forwarded-For solo ante proxies de confianza (loopback).
"""

import os
import sys
import hmac
import ipaddress
from datetime import datetime, timezone
from functools import wraps
from flask import request, session, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dashboard.core.database import get_db
from config import ADMIN_PASS

# Redes de proxies de confianza (por defecto: loopback IPv4 e IPv6)
TRUSTED_PROXIES = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128")
]
_RAW_TRUSTED = os.getenv("TRUSTED_PROXIES", "").strip()
if _RAW_TRUSTED:
    for _cidr in _RAW_TRUSTED.split(","):
        _cidr = _cidr.strip()
        if _cidr:
            try:
                TRUSTED_PROXIES.append(ipaddress.ip_network(_cidr, strict=False))
            except ValueError:
                print(f"⚠️ Dashboard Auth: Regla de proxy de confianza inválida: {_cidr}", file=sys.stderr)


def resolve_client_ip_dashboard(req) -> str:
    """Resuelve la IP del cliente de forma segura.

    Si el peer directo (socket) NO es un proxy de confianza, se devuelve la IP
    del socket y se ignoran por completo las cabeceras X-Forwarded-For o X-Real-IP.
    Si el peer directo ES de confianza (ej. Caddy o Nginx en 127.0.0.1), se recorre
    la cadena X-Forwarded-For de derecha a izquierda descartando proxies de confianza
    hasta llegar a la primera IP externa no confiable.
    """
    peer = req.remote_addr or ""
    if not peer:
        return "127.0.0.1"

    try:
        peer_obj = ipaddress.ip_address(peer)
    except ValueError:
        return peer

    # Si la conexión directa no proviene de un proxy de confianza, devolver socket IP
    if not any(peer_obj in net for net in TRUSTED_PROXIES):
        return peer

    # Viene de un proxy de confianza: inspeccionar cabecera X-Forwarded-For
    xff = req.headers.get("X-Forwarded-For")
    if xff:
        chain = [ip.strip() for ip in xff.split(",") if ip.strip()]
        for ip in reversed(chain):
            try:
                ip_obj = ipaddress.ip_address(ip)
                if any(ip_obj in net for net in TRUSTED_PROXIES):
                    continue
                return ip  # Primera IP no confiable de derecha a izquierda
            except ValueError:
                pass
        return peer

    real_ip = req.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return peer


def is_localhost_ip(ip_str: str) -> bool:
    """Determina si una dirección IP pertenece estrictamente a localhost (loopback)."""
    if not ip_str:
        return False
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        return ip_obj.is_loopback
    except ValueError:
        return False


def is_localhost_request(req) -> bool:
    """Verifica si la petición HTTP proviene efectivamente de localhost."""
    client_ip = resolve_client_ip_dashboard(req)
    return is_localhost_ip(client_ip)


def verify_credentials(username: str, password: str, req):
    """Verifica las credenciales de acceso aplicando las reglas de segregación.

    Retorna una tupla: (success: bool, message: str, user_dict: dict | None)
    """
    if not username or not password:
        return False, "Debe proporcionar usuario y contraseña.", None

    uname = username.strip()
    is_local = is_localhost_request(req)

    # 1. Caso exclusivo: Usuario 'admin'
    if uname.lower() == "admin":
        if not is_local:
            client_ip = resolve_client_ip_dashboard(req)
            return (
                False,
                f"Acceso denegado: El usuario 'admin' solo puede iniciar sesión desde localhost. Conexión detectada desde: {client_ip}",
                None
            )

        current_admin_pass = os.getenv("ADMIN_PASS", ADMIN_PASS)
        if not current_admin_pass:
            return (
                False,
                "ADMIN_PASS no está configurado en el archivo .env. Configure la clave e intente nuevamente.",
                None
            )

        if hmac.compare_digest(password, current_admin_pass):
            user_data = {
                "username": "admin",
                "role": "admin",
                "is_local": True,
                "is_remote_account": False
            }
            return True, "Autenticación exitosa.", user_data
        else:
            return False, "Contraseña incorrecta para el usuario admin.", None

    # 2. Caso: Usuarios remotos registrados en MongoDB
    try:
        db = get_db()
        user_doc = db.dashboard_users.find_one({"username": uname.lower()})
        if not user_doc:
            return False, "Usuario o contraseña inválidos.", None

        if not user_doc.get("is_active", True):
            return False, "La cuenta de usuario está desactivada o suspendida.", None

        pw_hash = user_doc.get("password_hash", "")
        if not pw_hash or not check_password_hash(pw_hash, password):
            return False, "Usuario o contraseña inválidos.", None

        # Actualizar último acceso
        db.dashboard_users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"last_login": datetime.now(timezone.utc)}}
        )

        user_data = {
            "username": user_doc["username"],
            "role": user_doc.get("role", "operator"),
            "is_local": is_local,
            "is_remote_account": True
        }
        return True, "Autenticación exitosa.", user_data

    except Exception as e:
        return False, f"Error al verificar credenciales con la base de datos: {e}", None


# --- Operaciones CRUD para Usuarios Remotos en MongoDB ---

def list_dashboard_users():
    """Lista todos los usuarios remotos registrados en MongoDB sin exponer hashes."""
    db = get_db()
    users = []
    for doc in db.dashboard_users.find().sort("username", 1):
        users.append({
            "id": str(doc.get("_id", "")),
            "username": doc.get("username", ""),
            "role": doc.get("role", "operator"),
            "is_active": doc.get("is_active", True),
            "created_by": doc.get("created_by", "system"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            "last_login": doc.get("last_login").isoformat() if doc.get("last_login") else None
        })
    return users


def create_dashboard_user(username: str, password: str, role: str = "operator", created_by: str = "admin"):
    """Crea un nuevo usuario remoto con contraseña encriptada en MongoDB."""
    uname = username.strip().lower()
    if not uname:
        return False, "El nombre de usuario no puede estar vacío."

    if uname == "admin":
        return False, "El nombre 'admin' está reservado exclusivamente para la administración local (.env)."

    if len(uname) < 3 or len(uname) > 32:
        return False, "El nombre de usuario debe tener entre 3 y 32 caracteres."

    if not uname.replace("_", "").replace("-", "").isalnum():
        return False, "El nombre de usuario solo puede contener letras, números, guiones y guiones bajos."

    if not password or len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    valid_roles = ["admin", "operator"]
    role = role.strip().lower()
    if role not in valid_roles:
        return False, f"Rol inválido. Roles permitidos: {', '.join(valid_roles)}."

    db = get_db()
    existing = db.dashboard_users.find_one({"username": uname})
    if existing:
        return False, f"El usuario '{uname}' ya existe."

    hashed = generate_password_hash(password)
    doc = {
        "username": uname,
        "password_hash": hashed,
        "role": role,
        "is_active": True,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc),
        "last_login": None
    }
    db.dashboard_users.insert_one(doc)
    return True, f"Usuario '{uname}' creado exitosamente."


def update_dashboard_user(username: str, role: str = None, is_active: bool = None):
    """Actualiza el rol o estado de activación de un usuario remoto."""
    uname = username.strip().lower()
    if uname == "admin":
        return False, "No se puede modificar el usuario reservado 'admin' desde la base de datos."

    db = get_db()
    user = db.dashboard_users.find_one({"username": uname})
    if not user:
        return False, f"Usuario '{uname}' no encontrado."

    update_fields = {}
    if role is not None:
        role_clean = role.strip().lower()
        if role_clean not in ["admin", "operator"]:
            return False, "Rol inválido. Debe ser 'admin' u 'operator'."
        update_fields["role"] = role_clean

    if is_active is not None:
        update_fields["is_active"] = bool(is_active)

    if not update_fields:
        return True, "No se realizaron cambios."

    db.dashboard_users.update_one({"username": uname}, {"$set": update_fields})
    return True, f"Usuario '{uname}' actualizado correctamente."


def reset_dashboard_user_password(username: str, new_password: str):
    """Restablece la contraseña de un usuario remoto con nuevo hash."""
    uname = username.strip().lower()
    if uname == "admin":
        return False, "La contraseña del usuario 'admin' solo puede modificarse en el archivo .env (ADMIN_PASS)."

    if not new_password or len(new_password) < 6:
        return False, "La nueva contraseña debe tener al menos 6 caracteres."

    db = get_db()
    user = db.dashboard_users.find_one({"username": uname})
    if not user:
        return False, f"Usuario '{uname}' no encontrado."

    hashed = generate_password_hash(new_password)
    db.dashboard_users.update_one(
        {"username": uname},
        {"$set": {"password_hash": hashed}}
    )
    return True, f"Contraseña actualizada para el usuario '{uname}'."


def delete_dashboard_user(username: str):
    """Elimina un usuario remoto de MongoDB."""
    uname = username.strip().lower()
    if uname == "admin":
        return False, "El usuario 'admin' no puede ser eliminado."

    db = get_db()
    res = db.dashboard_users.delete_one({"username": uname})
    if res.deleted_count == 0:
        return False, f"Usuario '{uname}' no encontrado."
    return True, f"Usuario '{uname}' eliminado exitosamente."


# --- Helpers de Sesión y Decoradores ---

def login_user_session(user_dict: dict):
    """Almacena el diccionario de usuario en la sesión de Flask."""
    session["user"] = user_dict
    session.permanent = True


def logout_user_session():
    """Limpia la sesión de usuario activa."""
    session.pop("user", None)


def get_current_user():
    """Retorna los datos del usuario logueado en la sesión actual, o None."""
    return session.get("user")


def login_required(f):
    """Decorador para proteger vistas y endpoints requiriendo sesión activa."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            if request.path.startswith("/api/") or request.is_json:
                return jsonify({"error": "No autenticado. Inicie sesión para continuar."}), 401
            return redirect(url_for("auth_bp.login_page", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorador para endpoints que requieren rol de administrador."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user")
        if not user:
            if request.path.startswith("/api/") or request.is_json:
                return jsonify({"error": "No autenticado."}), 401
            return redirect(url_for("auth_bp.login_page", next=request.path))
        if user.get("role") != "admin":
            if request.path.startswith("/api/") or request.is_json:
                return jsonify({"error": "Acceso denegado. Se requiere rol de administrador."}), 403
            return redirect(url_for("frontend_bp.index"))
        return f(*args, **kwargs)
    return decorated_function
