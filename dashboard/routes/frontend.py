import os
from flask import Blueprint, render_template, send_from_directory, current_app
from dashboard.core import REPO_ROOT

frontend_bp = Blueprint("frontend", __name__)

@frontend_bp.route("/")
def index():
    """Sirve la interfaz gráfica web principal del dashboard."""
    return render_template("index.html")

@frontend_bp.route("/favicon.ico")
def favicon():
    """Sirve el favicon estático del dashboard."""
    return current_app.send_static_file("favicon.svg")

@frontend_bp.route("/outputs/images/<path:filename>")
def serve_output_image(filename):
    """Sirve imágenes generadas dinámicamente por los modelos de imagen."""
    image_dir = os.getenv("IMAGE_OUTPUT_DIR", str(REPO_ROOT / "outputs" / "images"))
    return send_from_directory(image_dir, filename)
