#!/usr/bin/env bash
# ==============================================================================
# Script de Instalación del Servicio Systemd para Evaluador RAG (CRAG)
# Servicio: vllm-evaluator.service
# Modelo:   twil-lm3-q4_k_m.gguf (SmolLM3 3.1B GRPO Logic / Inferencia Deductiva)
# Puerto:   18300
# Cumple con el 4to Invariante MEA (Anti-Hardcoded Paths y Portabilidad) y Ley 1
# ==============================================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="vllm-evaluator"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
LAUNCHER_SCRIPT="${PROJECT_DIR}/llama-evaluator-srv.sh"

echo "============================================================"
echo "⚖️  Configurando Servicio Systemd para Evaluador RAG (CRAG)"
echo "============================================================"
echo "📍 Directorio del Proyecto: ${PROJECT_DIR}"
echo "👤 Usuario del Servicio:   root (para bloqueo de RAM con mlock)"
echo "🚀 Script Lanzador:        ${LAUNCHER_SCRIPT}"
echo "🏷️  Nombre de Servicio:     ${SERVICE_NAME}.service"
echo "============================================================"

if [ ! -f "${LAUNCHER_SCRIPT}" ]; then
    echo "❌ Error: No se encontró el script lanzador en ${LAUNCHER_SCRIPT}." >&2
    exit 1
fi

# Verificar permisos de root / sudo
if [ "$EUID" -ne 0 ]; then
    echo "🔒 Solicitando permisos de administrador (sudo) para crear el servicio..."
    exec sudo "$0" "$@"
fi

# Crear el archivo de servicio systemd con proteccion de puerto
cat <<'SERVICE_DEF' > "${SERVICE_PATH}"
[Unit]
Description=vLLM Suite Evaluador RAG de Suficiencia (CRAG / twil-lm3)
After=network.target nvidia-persistenced.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=##PROJECT_DIR##

# Verificación de disponibilidad de puerto antes de arrancar
ExecStartPre=##PROJECT_DIR##/check_service_conflict.sh "" 18300

ExecStart=##PROJECT_DIR##/llama-evaluator-srv.sh
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
echo "📌 Comandos útiles:"
echo "  • Iniciar:   sudo systemctl start ${SERVICE_NAME}"
echo "  • Detener:   sudo systemctl stop ${SERVICE_NAME}"
echo "  • Reiniciar: sudo systemctl restart ${SERVICE_NAME}"
echo "  • Estado:    sudo systemctl status ${SERVICE_NAME}"
echo "  • Ver logs:  sudo journalctl -u ${SERVICE_NAME} -f"
echo "============================================================"
