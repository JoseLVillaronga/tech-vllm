#!/usr/bin/env bash
# ==============================================================================
# Lanzador Dinámico de llama-server para Microservicio de Visión en RAM (CPU)
# Cumple con el 4to Invariante MEA (Anti-Hardcoded Paths y Portabilidad)
# Diseñado para ejecutar Qwen2.5-VL-3B-Instruct 100% en RAM sin tocar VRAM
# ==============================================================================
set -e

# Forzar ejecucion 100% en CPU (0 MB de VRAM)
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

# 3. Resolver directorio de llama.cpp evitando rutas /root
if [[ -z "${LLAMA_DIR}" || "${LLAMA_DIR}" == /root* || "${LLAMA_DIR}" == *"\$HOME"* ]]; then
    RESOLVED_LLAMA_DIR="${USER_HOME}/llama.cpp"
else
    RESOLVED_LLAMA_DIR="${LLAMA_DIR}"
fi
LLAMA_BIN="${RESOLVED_LLAMA_DIR}/build/bin/llama-server"

# Validar existencia del binario llama-server
if [ ! -f "${LLAMA_BIN}" ]; then
    echo "❌ Error: No se encontró llama-server en ${LLAMA_BIN}" >&2
    exit 1
fi

# 4. Resolver ruta del modelo GGUF y mmproj
RAW_MODEL="${VISION_MODEL:-${RESOLVED_LLAMA_DIR}/models/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf}"
MODEL_PATH="${RAW_MODEL/\$LLAMA_DIR/$RESOLVED_LLAMA_DIR}"
MODEL_PATH="${MODEL_PATH/\$HOME/$USER_HOME}"

if [[ "${MODEL_PATH}" == /root* || "${MODEL_PATH}" != /* ]]; then
    MODEL_PATH="${RESOLVED_LLAMA_DIR}/models/$(basename "${MODEL_PATH}")"
fi

if [ ! -f "${MODEL_PATH}" ]; then
    echo "❌ Error: No se encontró el archivo del modelo de visión en ${MODEL_PATH}" >&2
    exit 1
fi

RAW_MMPROJ="${VISION_MMPROJ:-${RESOLVED_LLAMA_DIR}/models/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf}"
MMPROJ_PATH="${RAW_MMPROJ/\$LLAMA_DIR/$RESOLVED_LLAMA_DIR}"
MMPROJ_PATH="${MMPROJ_PATH/\$HOME/$USER_HOME}"

if [[ "${MMPROJ_PATH}" == /root* || "${MMPROJ_PATH}" != /* ]]; then
    MMPROJ_PATH="${RESOLVED_LLAMA_DIR}/models/$(basename "${MMPROJ_PATH}")"
fi

if [ ! -f "${MMPROJ_PATH}" ]; then
    echo "❌ Error: No se encontró el archivo mmproj en ${MMPROJ_PATH}" >&2
    exit 1
fi

# 5. Parámetros de Inferencia en RAM (CPU)
PORT="${VISION_PORT:-18200}"
ALIAS="${VISION_ALIAS:-Qwen2.5-VL-3B-Instruct}"
CTX_SIZE="${VISION_CTX_SIZE:-8192}"
BATCH_SIZE="${VISION_BATCH_SIZE:-2048}"
UBATCH_SIZE="${VISION_UBATCH_SIZE:-512}"
GPU_LAYERS="${VISION_GPU_LAYERS:-0}"
THREADS="${VISION_THREADS:-8}"
AUTH_KEY="${API_KEY:-}"

echo "============================================================"
echo "👁️ Iniciando Microservicio de Visión en RAM (CPU)"
echo "============================================================"
echo "👤 Usuario Ejecutor: $(whoami) (Directorio Base: ${USER_HOME})"
echo "📍 Binario:          ${LLAMA_BIN}"
echo "📦 Modelo:           ${MODEL_PATH}"
echo "🏷️ Alias:            ${ALIAS}"
echo "👁️ Proyector Visión:  ${MMPROJ_PATH}"
echo "🔌 Puerto Backend:   ${PORT}"
echo "🧠 Contexto Máximo:  ${CTX_SIZE} tokens"
echo "⚡ Batch Lógico:     ${BATCH_SIZE}"
echo "🚀 Micro-Batch (uB): ${UBATCH_SIZE}"
echo "🎮 GPU Layers:       ${GPU_LAYERS} (Modo: 100% RAM / CPU)"
echo "🧵 Hilos CPU:        ${THREADS}"
echo "============================================================"

# Ejecutar llama-server reemplazando el proceso actual
exec "${LLAMA_BIN}" \
  --model "${MODEL_PATH}" \
  --alias "${ALIAS}" \
  --mmproj "${MMPROJ_PATH}" \
  --no-mmproj-offload \
  --ctx-size "${CTX_SIZE}" \
  --batch-size "${BATCH_SIZE}" \
  --ubatch-size "${UBATCH_SIZE}" \
  --gpu-layers "${GPU_LAYERS}" \
  --threads "${THREADS}" \
  --port "${PORT}" \
  --api-key "${AUTH_KEY}"
