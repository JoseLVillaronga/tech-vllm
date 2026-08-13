#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para vLLM Suite Dashboard
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"
APP_SCRIPT="${PROJECT_DIR}/app_dashboard.py"
SERVICE_NAME="vllm-dashboard"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

# Intentar extraer el usuario de systemd configurado en el archivo .env
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
    ENV_USER=$(grep -E "^USER_SYSTEMD=" "${ENV_FILE}" | cut -d'=' -f2 | tr -d '"'\'' ')
fi

SERVICE_USER="${ENV_USER:-${SUDO_USER:-$USER}}"

echo "============================================================"
echo "⚙️ Configurando Servicio Systemd para vLLM Suite Dashboard"
echo "============================================================"
echo "📍 Directorio del Proyecto: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio: ${SERVICE_USER}"
echo "🐍 Python Venv: ${VENV_PYTHON}"
echo "============================================================"

# Verificar entorno virtual y script
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "❌ Error: No se encontró el entorno virtual en ${VENV_PYTHON}."
    exit 1
fi

if [ ! -f "${APP_SCRIPT}" ]; then
    echo "❌ Error: No se encontró app_dashboard.py."
    exit 1
fi

# Solicitar privilegios de sudo para systemd
if [ "$EUID" -ne 0 ]; then
    echo "🔒 Solicitando permisos de administrador (sudo)..."
    exec sudo "$0" "$@"
fi

# Crear archivo de servicio
cat <<EOF > "${SERVICE_PATH}"
[Unit]
Description=vLLM Local Suite Administration Dashboard Web GUI
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} ${APP_SCRIPT}
Restart=always
RestartSec=10
Environment=PATH=${PROJECT_DIR}/venv/bin:/usr/local/cuda/bin:/usr/bin:/bin
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Archivo de servicio creado en ${SERVICE_PATH}"

echo "🔄 Recargando systemd daemon..."
systemctl daemon-reload

echo "🚀 Habilitando inicio automático del Dashboard..."
systemctl enable "${SERVICE_NAME}"

echo "▶️ Iniciando el servicio vLLM Dashboard..."
systemctl start "${SERVICE_NAME}"

echo "============================================================"
echo "🎉 Servicio vLLM Dashboard instalado e iniciado correctamente!"
echo "============================================================"
echo "📌 Comandos útiles para administrar el servicio:"
echo "  • Ver estado:     sudo systemctl status ${SERVICE_NAME}"
echo "  • Ver logs:       sudo journalctl -u ${SERVICE_NAME} -f"
echo "  • Detener:        sudo systemctl stop ${SERVICE_NAME}"
echo "  • Reiniciar:      sudo systemctl restart ${SERVICE_NAME}"
echo "  • Dashboard Web:  Accede a http://localhost:8004"
echo "============================================================"
