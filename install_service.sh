#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para vLLM (Gemma 4 26B)
# ==============================================================================

set -e

# Detectar directorio del proyecto, usuario y ejecutable de Python en venv
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"
APP_SCRIPT="${PROJECT_DIR}/app.py"
SERVICE_NAME="vllm"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

echo "============================================================"
echo "⚙️ Configurando Servicio Systemd para vLLM Server"
echo "============================================================"
echo "📍 Directorio del Proyecto: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio: ${SERVICE_USER}"
echo "🐍 Python Venv: ${VENV_PYTHON}"
echo "============================================================"

# Verificar que el entorno virtual y app.py existan
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "❌ Error: No se encontró el entorno virtual en ${VENV_PYTHON}."
    echo "Asegúrate de haber creado el venv ejecutando 'python -m venv venv' antes de instalar el servicio."
    exit 1
fi

if [ ! -f "${APP_SCRIPT}" ]; then
    echo "❌ Error: No se encontró app.py en ${APP_SCRIPT}."
    exit 1
fi

# Verificar permisos de root / sudo para escribir en /etc/systemd/system/
if [ "$EUID" -ne 0 ]; then
    echo "🔒 Solicitando permisos de administrador (sudo) para crear el servicio..."
    exec sudo "$0" "$@"
fi

# Crear el archivo de servicio systemd
cat <<EOF > "${SERVICE_PATH}"
[Unit]
Description=vLLM OpenAI API Server (Gemma 4 26B)
After=network.target nvidia-persistenced.service
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

# Recargar daemon de systemd, habilitar e iniciar el servicio
echo "🔄 Recargando systemd daemon..."
systemctl daemon-reload

echo "🚀 Habilitando inicio automático del servicio con el sistema..."
systemctl enable "${SERVICE_NAME}"

echo "▶️ Iniciando el servicio vLLM..."
systemctl start "${SERVICE_NAME}"

echo "============================================================"
echo "🎉 Servicio vLLM instalado e iniciado correctamente!"
echo "============================================================"
echo "📌 Comandos útiles para administrar el servicio:"
echo "  • Ver estado:     sudo systemctl status ${SERVICE_NAME}"
echo "  • Ver logs:       sudo journalctl -u ${SERVICE_NAME} -f"
echo "  • Detener:        sudo systemctl stop ${SERVICE_NAME}"
echo "  • Reiniciar:      sudo systemctl restart ${SERVICE_NAME}"
echo "============================================================"
