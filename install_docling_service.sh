#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para Docling Serve
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"

# Intentar extraer el usuario de systemd si está configurado en .env
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
    ENV_USER=$(grep -E "^USER_SYSTEMD=" "${ENV_FILE}" | cut -d'=' -f2 | tr -d '"'\'' ')
    if [ -n "${ENV_USER}" ]; then
        SERVICE_USER="${ENV_USER}"
    fi
fi

# Detectar el binario de docling-serve
if command -v docling-serve >/dev/null 2>&1; then
    DOCLING_BIN="$(command -v docling-serve)"
elif [ -f "/home/${SERVICE_USER}/anaconda3/bin/docling-serve" ]; then
    DOCLING_BIN="/home/${SERVICE_USER}/anaconda3/bin/docling-serve"
elif [ -f "${PROJECT_DIR}/venv/bin/docling-serve" ]; then
    DOCLING_BIN="${PROJECT_DIR}/venv/bin/docling-serve"
elif [ -f "/home/${SERVICE_USER}/.local/bin/docling-serve" ]; then
    DOCLING_BIN="/home/${SERVICE_USER}/.local/bin/docling-serve"
elif [ -f "/usr/local/bin/docling-serve" ]; then
    DOCLING_BIN="/usr/local/bin/docling-serve"
else
    DOCLING_BIN="/home/jose/anaconda3/bin/docling-serve"
fi

SERVICE_NAME="docling"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
PORT="5020"
HOST="0.0.0.0"

echo "============================================================"
echo "⚙️  Configurando Servicio Systemd para Docling Serve"
echo "============================================================"
echo "📍 Directorio de Trabajo: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio:   ${SERVICE_USER}"
echo "🚀 Binario docling-serve: ${DOCLING_BIN}"
echo "🌐 Host/Puerto:           ${HOST}:${PORT}"
echo "============================================================"

# Verificar que exista el binario
if [ ! -f "${DOCLING_BIN}" ]; then
    echo "⚠️ Advertencia: No se detectó docling-serve en ${DOCLING_BIN}."
    echo "Si está en otro entorno, asegúrate de instalarlo con: pip install docling-serve"
fi

# Verificar permisos de root / sudo para escribir en /etc/systemd/system/
if [ "$EUID" -ne 0 ]; then
    echo "🔒 Solicitando permisos de administrador (sudo) para crear el servicio..."
    exec sudo "$0" "$@"
fi

# Crear el archivo de servicio systemd
cat <<EOF > "${SERVICE_PATH}"
[Unit]
Description=Docling Serve API (Document Processing & OCR Engine)
After=network.target nvidia-persistenced.service
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="HOME=/home/${SERVICE_USER}"
Environment="PATH=/home/${SERVICE_USER}/anaconda3/bin:${PROJECT_DIR}/venv/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=${DOCLING_BIN} run --host ${HOST} --port ${PORT}
Restart=always
RestartSec=10
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
echo "  • Swagger Docs:   http://localhost:${PORT}/docs"
echo "  • Scalar Docs:    http://localhost:${PORT}/scalar"
echo "============================================================"
