#!/usr/bin/env bash
# ==============================================================================
# Script de Instalacion del Servicio Systemd para llama-server (vllm-llama.service)
# Cumple con el 5to Invariante MEA (Anti-Hardcoded Paths y Ejecucion Segura)
# ==============================================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="vllm-llama"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
LAUNCHER_SCRIPT="${PROJECT_DIR}/llama-srv.sh"

echo "============================================================"
echo "⚙️ Configurando Servicio Systemd para llama-server (vLLM Suite)"
echo "============================================================"
echo "📍 Directorio del Proyecto: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio:   root (para bloqueo de RAM con mlock)"
echo "🚀 Script Lanzador:        ${LAUNCHER_SCRIPT}"
echo "============================================================"

if [ ! -f "${LAUNCHER_SCRIPT}" ]; then
    echo "❌ Error: No se encontro el script lanzador en ${LAUNCHER_SCRIPT}." >&2
    exit 1
fi

# Verificar permisos de root / sudo
if [ "$EUID" -ne 0 ]; then
    echo "🔒 Solicitando permisos de administrador (sudo) para crear el servicio..."
    exec sudo "$0" "$@"
fi

# Crear el archivo de servicio systemd con proteccion de colision
cat <<'SERVICE_DEF' > "${SERVICE_PATH}"
[Unit]
Description=vLLM Suite Llama.cpp Engine (Qwen 3.6 MoE)
After=network.target nvidia-persistenced.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=##PROJECT_DIR##

# Control de Exclusion Mutua: si vllm.service esta activo o el puerto esta ocupado, aborta inmediatamente
ExecStartPre=/bin/bash -c 'if systemctl is-active --quiet vllm.service; then echo "❌ Conflicto: vllm.service esta en ejecucion. Detengalo antes de iniciar vllm-llama." >&2; exit 1; fi'
ExecStartPre=/bin/bash -c 'PORT=$(grep -E "^(LLAMA_PORT|GEMMA_BACKEND_PORT)=" ##PROJECT_DIR##/.env 2>/dev/null | tail -n 1 | cut -d= -f2 || echo 18100); if ss -tulpn | grep -q ":${PORT} "; then echo "❌ Conflicto: El puerto ${PORT} ya esta en uso. Detenga el proceso que lo ocupa antes de iniciar vllm-llama." >&2; exit 1; fi'

ExecStart=##PROJECT_DIR##/llama-srv.sh
Restart=on-failure
RestartSec=5
Environment=PATH=/usr/local/cuda/bin:/usr/bin:/bin
StandardOutput=journal
StandardError=journal
LimitNOFILE=65536
LimitMEMLOCK=infinity

[Install]
WantedBy=multi-user.target
SERVICE_DEF

# Reemplazar placeholder con directorio real
sed -i "s|##PROJECT_DIR##|${PROJECT_DIR}|g" "${SERVICE_PATH}"

echo "✅ Archivo de servicio creado en ${SERVICE_PATH}"

echo "🔄 Recargando systemd daemon..."
systemctl daemon-reload

echo "🚀 Habilitando servicio ${SERVICE_NAME}..."
systemctl enable "${SERVICE_NAME}"

echo "============================================================"
echo "🎉 Servicio ${SERVICE_NAME} configurado exitosamente!"
echo "============================================================"
echo "📌 Comandos utiles:"
echo "  • Iniciar:   sudo systemctl start ${SERVICE_NAME}"
echo "  • Detener:   sudo systemctl stop ${SERVICE_NAME}"
echo "  • Estado:    sudo systemctl status ${SERVICE_NAME}"
echo "  • Ver logs:  sudo journalctl -u ${SERVICE_NAME} -f"
echo "============================================================"
