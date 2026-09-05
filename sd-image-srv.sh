#!/usr/bin/env bash
# ==============================================================================
# Lanzador Dinámico de sd-server para Microservicio de Difusión en RAM (CPU)
# Cumple con el 4to Invariante MEA (Anti-Hardcoded Paths y Portabilidad)
# Diseñado para ejecutar SDXL-Turbo (GGUF) 100% en RAM sin tocar VRAM (0 MB)
# ==============================================================================
set -e

# Forzar ejecución 100% en CPU (0 MB de VRAM)
export CUDA_VISIBLE_DEVICES=""

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Cargar variables desde .env si existe
if [ -f "${PROJECT_DIR}/.env" ]; then
    set -a
    source "${PROJECT_DIR}/.env"
    set +a
fi

# 2. Resolución dinámica del usuario y home real
TARGET_USER="${USER_SYSTEMD:-${SUDO_USER:-$(stat -c '%U' "${PROJECT_DIR}" 2>/dev/null || echo "jose")}}"
if [ "${TARGET_USER}" = "root" ]; then
    TARGET_USER="$(stat -c '%U' "${PROJECT_DIR}" 2>/dev/null || echo "jose")"
fi
USER_HOME=$(eval echo "~${TARGET_USER}")

# 3. Resolver directorio de stable-diffusion.cpp
if [[ -z "${SD_DIR}" || "${SD_DIR}" == /root* || "${SD_DIR}" == *"\$HOME"* ]]; then
    RESOLVED_SD_DIR="${USER_HOME}/stable-diffusion.cpp"
else
    RESOLVED_SD_DIR="${SD_DIR}"
fi
SD_BIN="${RESOLVED_SD_DIR}/build/bin/sd-server"

# Validar existencia del binario sd-server
if [ ! -f "${SD_BIN}" ]; then
    echo "❌ Error: No se encontró sd-server en ${SD_BIN}" >&2
    exit 1
fi

# 4. Resolver ruta del modelo GGUF de SDXL-Turbo
RAW_MODEL="${SD_MODEL:-${RESOLVED_SD_DIR}/models/sd_xl_turbo_1.0.q8_0.gguf}"
MODEL_PATH="${RAW_MODEL/\$SD_DIR/$RESOLVED_SD_DIR}"
MODEL_PATH="${MODEL_PATH/\$HOME/$USER_HOME}"

if [[ "${MODEL_PATH}" == /root* || "${MODEL_PATH}" != /* ]]; then
    MODEL_PATH="${RESOLVED_SD_DIR}/models/$(basename "${MODEL_PATH}")"
fi

if [ ! -f "${MODEL_PATH}" ]; then
    echo "❌ Error: No se encontró el archivo del modelo SDXL-Turbo en ${MODEL_PATH}" >&2
    exit 1
fi

# 5. Parámetros de Inferencia en RAM (CPU)
PORT="${IMAGE_BACKEND_PORT:-18004}"
THREADS="${SD_THREADS:-8}"
STEPS="${SD_STEPS:-1}"
CFG_SCALE="${SD_CFG_SCALE:-1.0}"
SAMPLING_METHOD="${SD_SAMPLING_METHOD:-euler_a}"

echo "============================================================"
echo "🎨 Iniciando Microservicio de Difusión en RAM (CPU / GGUF)"
echo "============================================================"
echo "👤 Usuario Ejecutor: $(whoami) (Directorio Base: ${USER_HOME})"
echo "📍 Binario:          ${SD_BIN}"
echo "📦 Modelo:           ${MODEL_PATH}"
echo "🔌 Puerto Backend:   ${PORT}"
echo "🧵 Hilos CPU:        ${THREADS}"
echo "🔢 Pasos (Steps):    ${STEPS} (ADD Distilled)"
echo "🎛️ CFG Scale:        ${CFG_SCALE}"
echo "🎯 Método Muestreo:  ${SAMPLING_METHOD}"
echo "🎮 VRAM Utilizada:   0 MB (Modo: 100% RAM / CPU)"
echo "============================================================"

# Ejecutar sd-server reemplazando el proceso actual
exec "${SD_BIN}" \
  -m "${MODEL_PATH}" \
  --listen-ip 127.0.0.1 \
  --listen-port "${PORT}" \
  --threads "${THREADS}" \
  --steps "${STEPS}" \
  --cfg-scale "${CFG_SCALE}" \
  --sampling-method "${SAMPLING_METHOD}"
