#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Temporizador Systemd para Sincronización RAG (Teccam PDF -> LanceDB)
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
APP_SCRIPT="${PROJECT_DIR}/sync_rag_scheduled.sh"
SERVICE_NAME="vllm-rag-sync"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
TIMER_PATH="/etc/systemd/system/${SERVICE_NAME}.timer"

echo "============================================================"
echo "⚙️  Configurando Servicio y Temporizador Systemd para RAG Sync"
echo "============================================================"
echo "📍 Directorio del Proyecto: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio:   root (requerido para gestionar vllm.service)"
echo "📜 Script Orquestador:     ${APP_SCRIPT}"
echo "⏰ Frecuencia de Sincronía: 1 vez al día a la medianoche (00:00:00)"
echo "============================================================"

# Verificar entorno virtual y script
if [ ! -f "${VENV_PYTHON}" ]; then
    echo "❌ Error: No se encontró el entorno virtual en ${VENV_PYTHON}."
    exit 1
fi

if [ ! -f "${APP_SCRIPT}" ]; then
    echo "❌ Error: No se encontró sync_rag_scheduled.sh."
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
Description=vLLM Knowledge Base RAG Synchronizer with VRAM Management (Teccam PDF to LanceDB)
After=network.target vllm-embeddings.service

[Service]
Type=oneshot
User=root
WorkingDirectory=${PROJECT_DIR}
Environment="HOME=/root"
Environment="PATH=${PROJECT_DIR}/venv/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/bin/bash ${APP_SCRIPT}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Crear archivo de temporizador (Timer)
cat <<EOF > "${TIMER_PATH}"
[Unit]
Description=Timer para Sincronización Periódica de Base de Conocimiento RAG (Medianoche - 00:00)

[Timer]
OnCalendar=*-*-* 00:00:00
Persistent=true
RandomizedDelaySec=60

[Install]
WantedBy=timers.target
EOF

echo "✅ Archivos creados en ${SERVICE_PATH} y ${TIMER_PATH}"

echo "🔄 Recargando systemd daemon..."
systemctl daemon-reload

echo "🚀 Habilitando y activando temporizador ${SERVICE_NAME}.timer..."
systemctl enable --now "${SERVICE_NAME}.timer"

echo "============================================================"
echo "🎉 Temporizador ${SERVICE_NAME}.timer configurado e iniciado!"
echo "============================================================"
echo "📌 Comandos útiles:"
echo "  • Ver temporizadores: sudo systemctl list-timers | grep vllm-rag-sync"
echo "  • Ejecutar sync manual: sudo systemctl start ${SERVICE_NAME}.service"
echo "  • Ver logs de sync:    sudo journalctl -u ${SERVICE_NAME}.service -n 50"
echo "============================================================"
