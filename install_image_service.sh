#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para Generador de Imágenes (Diffusion)
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"

# Intentar extraer el usuario de systemd configurado en .env
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
    ENV_USER=$(grep -E "^USER_SYSTEMD=" "${ENV_FILE}" | cut -d'=' -f2 | tr -d '"'\'' ')
    if [ -n "${ENV_USER}" ]; then
        SERVICE_USER="${ENV_USER}"
    fi
fi

VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"
APP_SCRIPT="${PROJECT_DIR}/app_image.py"
SERVICE_NAME="vllm-image"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
PORT="18004"

echo "============================================================"
echo "⚙️  Configurando Servicio Systemd para Generador de Imágenes"
echo "============================================================"
echo "📍 Directorio del Proyecto: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio:   ${SERVICE_USER}"
echo "🐍 Python Venv:            ${VENV_PYTHON}"
echo "🌐 Puerto Interno:         ${PORT}"
echo "============================================================"

# Verificar entorno virtual y script
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "❌ Error: No se encontró el entorno virtual en ${VENV_PYTHON}."
    exit 1
fi

if [ ! -f "${APP_SCRIPT}" ]; then
    echo "❌ Error: No se encontró app_image.py."
    exit 1
fi

# Solicitar permisos de sudo para escribir en systemd
if [ "$EUID" -ne 0 ]; then
    echo "🔒 Solicitando permisos de administrador (sudo)..."
    exec sudo "$0" "$@"
fi

# Crear archivo de servicio
cat <<EOF > "${SERVICE_PATH}"
[Unit]
Description=vLLM OpenAI-Compatible Image Generation Server (Diffusion / SDXL-Turbo / FLUX)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} ${APP_SCRIPT}
Restart=always
RestartSec=5
Environment=PATH=${PROJECT_DIR}/venv/bin:/usr/local/cuda/bin:/usr/bin:/bin
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "${SERVICE_PATH}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "============================================================"
echo "✅ ¡Servicio ${SERVICE_NAME} instalado y activo en puerto ${PORT}!"
echo "Comandos útiles:"
echo "  - Ver logs: sudo journalctl -u ${SERVICE_NAME} -f"
echo "  - Estado:   systemctl status ${SERVICE_NAME}"
echo "  - Reiniciar: sudo systemctl restart ${SERVICE_NAME}"
echo "============================================================"
