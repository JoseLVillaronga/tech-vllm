#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para vLLM Speaker Diarization
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"
APP_SCRIPT="${PROJECT_DIR}/app_diarization.py"
SERVICE_NAME="vllm-diarization"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo "============================================================"
echo "⚙️ Configurando Servicio Systemd para vLLM Diarization Server"
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
    echo "❌ Error: No se encontró app_diarization.py."
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
Description=vLLM OpenAI-Compatible Speaker Diarization Server (PyAnnote)
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

echo "🚀 Habilitando inicio automático..."
systemctl enable "${SERVICE_NAME}"

echo "▶️ Iniciando el servicio vLLM Diarization..."
systemctl start "${SERVICE_NAME}"

echo "============================================================"
echo "🎉 Servicio vLLM Diarization instalado e iniciado correctamente!"
echo "============================================================"
echo "📌 Comandos útiles para administrar el servicio:"
echo "  • Ver estado:     sudo systemctl status ${SERVICE_NAME}"
echo "  • Ver logs:       sudo journalctl -u ${SERVICE_NAME} -f"
echo "  • Detener:        sudo systemctl stop ${SERVICE_NAME}"
echo "  • Reiniciar:      sudo systemctl restart ${SERVICE_NAME}"
echo "  • Documentación:  Accede a http://localhost:8003/docs para ver Swagger"
echo "============================================================"
