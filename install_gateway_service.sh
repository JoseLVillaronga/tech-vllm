#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para el Gateway Proxy de vLLM
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"
APP_SCRIPT="${PROJECT_DIR}/app_gateway.py"
SERVICE_NAME="vllm-gateway"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo "============================================================"
echo "⚙️ Configurando Servicio Systemd para vLLM API Gateway"
echo "============================================================"
echo "📍 Directorio del Proyecto: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio: ${SERVICE_USER}"
echo "============================================================"

if [ ! -f "${VENV_PYTHON}" ]; then
    echo "❌ Error: No se encontró el entorno virtual en ${VENV_PYTHON}."
    exit 1
fi

if [ ! -f "${APP_SCRIPT}" ]; then
    echo "❌ Error: No se encontró app_gateway.py en ${APP_SCRIPT}."
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "🔒 Solicitando permisos de administrador (sudo) para crear el servicio..."
    exec sudo "$0" "$@"
fi

# Crear el archivo de servicio systemd
cat <<EOF > "${SERVICE_PATH}"
[Unit]
Description=vLLM Suite API Security Gateway & Reverse Proxy
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
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Archivo de servicio creado en ${SERVICE_PATH}"

echo "🔄 Recargando systemd daemon..."
systemctl daemon-reload

echo "🚀 Habilitando inicio automático de vllm-gateway..."
systemctl enable "${SERVICE_NAME}"

echo "▶️ Iniciando el servicio vllm-gateway..."
systemctl start "${SERVICE_NAME}"

echo "============================================================"
echo "🎉 Servicio vllm-gateway instalado e iniciado correctamente!"
echo "============================================================"
