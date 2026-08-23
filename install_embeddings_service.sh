#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para Qwen3-Embedding (RAM / CPU)
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
APP_SCRIPT="${PROJECT_DIR}/app_embeddings.py"
SERVICE_NAME="vllm-embeddings"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
PORT="18005"

echo "============================================================"
echo "⚙️  Configurando Servicio Systemd para Qwen3-Embedding (RAM)"
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
    echo "❌ Error: No se encontró app_embeddings.py."
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
Description=vLLM OpenAI-Compatible Qwen3-Embedding Server (CUDA GPU / CPU Accelerated)
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="HOME=/home/${SERVICE_USER}"
Environment="PATH=${PROJECT_DIR}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=${VENV_PYTHON} ${APP_SCRIPT}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Archivo de servicio creado en ${SERVICE_PATH}"

echo "🔄 Recargando systemd daemon..."
systemctl daemon-reload

echo "🚀 Habilitando inicio automático de ${SERVICE_NAME}..."
systemctl enable "${SERVICE_NAME}"

echo "▶️ Iniciando el servicio ${SERVICE_NAME}..."
systemctl start "${SERVICE_NAME}"

echo "============================================================"
echo "🎉 Servicio ${SERVICE_NAME} instalado e iniciado correctamente!"
echo "============================================================"
echo "📌 Comandos útiles para administrar el servicio:"
echo "  • Ver estado:     sudo systemctl status ${SERVICE_NAME}"
echo "  • Ver logs:       sudo journalctl -u ${SERVICE_NAME} -f"
echo "  • Detener:        sudo systemctl stop ${SERVICE_NAME}"
echo "  • Reiniciar:      sudo systemctl restart ${SERVICE_NAME}"
echo "  • Documentación:  http://localhost:${PORT}/docs"
echo "============================================================"
