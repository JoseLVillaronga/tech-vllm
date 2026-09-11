"""
users.py - Rutas de administración de usuarios remotos para el Dashboard.

Permite a los administradores autenticados gestionar las cuentas de acceso remoto:
crear nuevos operadores/administradores, cambiar contraseñas, activar/suspender y eliminar.
"""

from flask import Blueprint, request, jsonify
from dashboard.core.auth_service import (
    admin_required,
    get_current_user,
    list_dashboard_users,
    create_dashboard_user,
    update_dashboard_user,
    reset_dashboard_user_password,
    delete_dashboard_user
)

users_bp = Blueprint("users_bp", __name__)


@users_bp.route("/api/users", methods=["GET"])
@admin_required
def get_users():
    """Retorna la lista completa de usuarios remotos registrados."""
    try:
        users = list_dashboard_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({"error": f"Error al obtener usuarios: {e}"}), 500


@users_bp.route("/api/users", methods=["POST"])
@admin_required
def create_user():
    """Crea un nuevo usuario remoto con contraseña encriptada."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    role = data.get("role", "operator")

    current_user = get_current_user() or {}
    creator = current_user.get("username", "admin")

    success, message = create_dashboard_user(
        username=username,
        password=password,
        role=role,
        created_by=creator
    )
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message}), 201


@users_bp.route("/api/users/<username>", methods=["PUT"])
@admin_required
def update_user(username: str):
    """Actualiza el rol o estado de activación de un usuario remoto."""
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    is_active = data.get("is_active")

    success, message = update_dashboard_user(
        username=username,
        role=role,
        is_active=is_active
    )
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message})


@users_bp.route("/api/users/<username>/password", methods=["PUT", "POST"])
@admin_required
def reset_password(username: str):
    """Restablece la contraseña de un usuario remoto."""
    data = request.get_json(silent=True) or {}
    new_password = data.get("password", "")

    if not new_password:
        return jsonify({"error": "Debe especificar la nueva contraseña."}), 400

    success, message = reset_dashboard_user_password(
        username=username,
        new_password=new_password
    )
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message})


@users_bp.route("/api/users/<username>", methods=["DELETE"])
@admin_required
def delete_user(username: str):
    """Elimina un usuario remoto registrado."""
    current_user = get_current_user() or {}
    if current_user.get("username", "").lower() == username.lower():
        return jsonify({"error": "No puede eliminar su propia cuenta activa."}), 400

    success, message = delete_dashboard_user(username)
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message})
