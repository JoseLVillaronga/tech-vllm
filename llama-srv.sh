#!/usr/bin/env bash
# ==============================================================================
# Lanzador Dinámico de llama-server para vLLM Suite
# Cumple con el 5to Invariante MEA (Anti-Hardcoded Paths y Multi-Usuario)
# ==============================================================================
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Cargar variables desde .env si existe
if [ -f "${PROJECT_DIR}/.env" ]; then
    set -a
    source "${PROJECT_DIR}/.env"
    set +a
fi

# 2. Resolución dinámica del usuario y home real
# Si se ejecuta como root (systemd), localiza el dueño del proyecto (ej: jose)
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

# 4. Resolver ruta del modelo GGUF
RAW_MODEL="${LLAMA_MODEL:-${RESOLVED_LLAMA_DIR}/models/Qwen3.6-35B-A3B-Q4_K_M.gguf}"
# Reemplazar variables $LLAMA_DIR o $HOME si venían como texto literal en .env
MODEL_PATH="${RAW_MODEL/\$LLAMA_DIR/$RESOLVED_LLAMA_DIR}"
MODEL_PATH="${MODEL_PATH/\$HOME/$USER_HOME}"

# Si se pasó un nombre simple o ruta que comienza con /root
if [[ "${MODEL_PATH}" == /root* || "${MODEL_PATH}" != /* ]]; then
    MODEL_PATH="${RESOLVED_LLAMA_DIR}/models/$(basename "${MODEL_PATH}")"
fi

if [ ! -f "${MODEL_PATH}" ]; then
    echo "❌ Error: No se encontró el archivo del modelo en ${MODEL_PATH}" >&2
    exit 1
fi

# 5. Parámetros de Inferencia con Fallbacks Deterministas
PORT="${LLAMA_PORT:-${GEMMA_BACKEND_PORT:-18100}}"
ALIAS="${LLAMA_ALIAS:-Qwen3.6-35B-A3B-Q4_K_M}"
CTX_SIZE="${LLAMA_CTX_SIZE:-131072}"
BATCH_SIZE="${LLAMA_BATCH_SIZE:-4096}"
GPU_LAYERS="${LLAMA_GPU_LAYERS:-256}"
N_CPU_MOE="${LLAMA_N_CPU_MOE:-18}"
REASONING="${LLAMA_REASONING:-off}"
THREADS="${LLAMA_THREADS:-8}"
LOAD_MODE="${LLAMA_LOAD_MODE:-mlock}"
AUTH_KEY="${API_KEY:-token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939}"

echo "============================================================"
echo "🦙 Iniciando llama-server para vLLM Suite"
echo "============================================================"
echo "👤 Usuario Ejecutor: $(whoami) (Directorio Base: ${USER_HOME})"
echo "📍 Binario:          ${LLAMA_BIN}"
echo "📦 Modelo:           ${MODEL_PATH}"
echo "🏷️ Alias:            ${ALIAS}"
echo "🔌 Puerto Backend:   ${PORT}"
echo "🧠 Contexto Máximo:  ${CTX_SIZE} tokens"
echo "⚡ Batch Size:       ${BATCH_SIZE}"
echo "🎮 GPU Layers:       ${GPU_LAYERS} (MoE CPU: ${N_CPU_MOE})"
echo "💭 Razonamiento:     ${REASONING}"
echo "🔒 Modo de Carga:    --load-mode ${LOAD_MODE}"
echo "🧵 Hilos CPU:        ${THREADS}"
echo "============================================================"

# Reemplazar la shell por el proceso llama-server para gestión nativa en systemd
exec "${LLAMA_BIN}" \
  --model "${MODEL_PATH}" \
  --alias "${ALIAS}" \
  --ctx-size "${CTX_SIZE}" \
  --batch-size "${BATCH_SIZE}" \
  --gpu-layers "${GPU_LAYERS}" \
  --n-cpu-moe "${N_CPU_MOE}" \
  --reasoning "${REASONING}" \
  --flash-attn on \
  --threads "${THREADS}" \
  --load-mode "${LOAD_MODE}" \
  --port "${PORT}" \
  --api-key "${AUTH_KEY}"
