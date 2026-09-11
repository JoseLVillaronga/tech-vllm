"""
auth.py - Rutas y endpoints para la autenticación y ciclo de vida de sesión.
"""

from flask import Blueprint, request, render_template, redirect, url_for, jsonify, session
from dashboard.core.auth_service import (
    resolve_client_ip_dashboard,
    is_localhost_request,
    verify_credentials,
    login_user_session,
    logout_user_session,
    get_current_user
)

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    """Renderiza el formulario de login o procesa la autenticación tradicional."""
    is_local = is_localhost_request(request)
    client_ip = resolve_client_ip_dashboard(request)

    # Si ya cuenta con sesión activa, redirigir al panel principal
    if session.get("user"):
        return redirect(url_for("frontend_bp.index"))

    next_url = request.args.get("next") or "/"

    if request.method == "POST":
        # Soporte para Content-Type application/x-www-form-urlencoded y application/json
        if request.is_json:
            data = request.get_json() or {}
            username = data.get("username", "")
            password = data.get("password", "")
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")

        success, message, user_data = verify_credentials(username, password, request)
        if not success:
            status_code = 403 if "Acceso denegado: El usuario 'admin' solo puede iniciar sesión desde localhost" in message else 401
            if request.is_json:
                return jsonify({"error": message}), status_code
            return render_template(
                "login.html",
                error=message,
                is_local=is_local,
                client_ip=client_ip,
                username=username,
                next=next_url
            ), status_code

        # Login exitoso
        login_user_session(user_data)
        if request.is_json:
            return jsonify({"success": True, "redirect": next_url, "user": user_data})
        return redirect(next_url)

    return render_template(
        "login.html",
        error=None,
        is_local=is_local,
        client_ip=client_ip,
        username="",
        next=next_url
    )


@auth_bp.route("/api/auth/login", methods=["POST"])
def api_login():
    """Endpoint REST JSON para autenticación desde frontend SPA."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Debe proporcionar usuario y contraseña."}), 400

    success, message, user_data = verify_credentials(username, password, request)
    if not success:
        status_code = 403 if "Acceso denegado" in message else 401
        return jsonify({"error": message}), status_code

    login_user_session(user_data)
    next_url = request.args.get("next") or "/"
    return jsonify({
        "success": True,
        "message": "Autenticación exitosa.",
        "user": user_data,
        "redirect": next_url
    })


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Cierra la sesión activa y redirige al login."""
    logout_user_session()
    if request.is_json:
        return jsonify({"success": True, "message": "Sesión finalizada."})
    return redirect(url_for("auth_bp.login_page"))


@auth_bp.route("/api/auth/me", methods=["GET"])
def api_me():
    """Informa el estado de sesión y contexto del cliente conectado."""
    user = get_current_user()
    is_local = is_localhost_request(request)
    client_ip = resolve_client_ip_dashboard(request)

    return jsonify({
        "authenticated": bool(user),
        "user": user,
        "is_local": is_local,
        "client_ip": client_ip
    })
