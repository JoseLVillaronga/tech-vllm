#!/usr/bin/env bash
# ==============================================================================
# Lanzador Dinámico de llama-server para Microservicio Evaluador de Suficiencia RAG
# Cumple con el 4to Invariante MEA (Anti-Hardcoded Paths y Portabilidad) y Ley 1
# Modelo: twil-lm3-q4_k_m.gguf (SmolLM3 3.1B fine-tune formal logic / reasoning)
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

# 4. Resolver ruta del modelo GGUF evaluador
RAW_MODEL="${EVALUATOR_MODEL:-${RESOLVED_LLAMA_DIR}/models/twil-lm3-q4_k_m.gguf}"
MODEL_PATH="${RAW_MODEL/\$LLAMA_DIR/$RESOLVED_LLAMA_DIR}"
MODEL_PATH="${MODEL_PATH/\$HOME/$USER_HOME}"

if [[ "${MODEL_PATH}" == /root* || "${MODEL_PATH}" != /* ]]; then
    MODEL_PATH="${RESOLVED_LLAMA_DIR}/models/$(basename "${MODEL_PATH}")"
fi

if [ ! -f "${MODEL_PATH}" ]; then
    echo "❌ Error: No se encontró el archivo del modelo evaluador en ${MODEL_PATH}" >&2
    exit 1
fi

# 5. Parámetros de Inferencia para twil-lm3 (SmolLM3 3.1B Logic/Reasoning)
PORT="${EVALUATOR_BACKEND_PORT:-${EVALUATOR_PORT:-18300}}"
ALIAS="${EVALUATOR_ALIAS:-twil-lm3-q4_k_m}"
CTX_SIZE="${EVALUATOR_CTX_SIZE:-8192}"
BATCH_SIZE="${EVALUATOR_BATCH_SIZE:-2048}"
UBATCH_SIZE="${EVALUATOR_UBATCH_SIZE:-512}"
GPU_LAYERS="${EVALUATOR_GPU_LAYERS:-99}"
THREADS="${EVALUATOR_THREADS:-8}"
PARALLEL="${EVALUATOR_PARALLEL:-1}"
CACHE_TYPE_K="${EVALUATOR_CACHE_TYPE_K:-q4_0}"
CACHE_TYPE_V="${EVALUATOR_CACHE_TYPE_V:-q4_0}"
AUTH_KEY="${API_KEY:-}"

echo "============================================================"
echo "⚖️ Iniciando Microservicio Evaluador de Suficiencia RAG (CRAG)"
echo "============================================================"
echo "👤 Usuario Ejecutor: $(whoami) (Directorio Base: ${USER_HOME})"
echo "📍 Binario:          ${LLAMA_BIN}"
echo "📦 Modelo:           ${MODEL_PATH}"
echo "🏷️ Alias:            ${ALIAS}"
echo "🔌 Puerto Backend:   ${PORT}"
echo "🧠 Contexto Máximo:  ${CTX_SIZE} tokens"
echo "⚡ Batch Lógico:     ${BATCH_SIZE}"
echo "🚀 Micro-Batch (uB): ${UBATCH_SIZE}"
echo "🎮 GPU Layers:       ${GPU_LAYERS} (99 = Aceleración GPU CUDA)"
echo "🧵 Hilos CPU:        ${THREADS}"
echo "👥 Slots Paralelos:  ${PARALLEL}"
echo "🗜️ KV Cache K:       ${CACHE_TYPE_K}"
echo "🗜️ KV Cache V:       ${CACHE_TYPE_V}"
echo "============================================================"

# Ejecutar llama-server reemplazando el proceso actual
exec "${LLAMA_BIN}" \
  --model "${MODEL_PATH}" \
  --alias "${ALIAS}" \
  --ctx-size "${CTX_SIZE}" \
  --batch-size "${BATCH_SIZE}" \
  --ubatch-size "${UBATCH_SIZE}" \
  --gpu-layers "${GPU_LAYERS}" \
  --threads "${THREADS}" \
  --parallel "${PARALLEL}" \
  --cache-type-k "${CACHE_TYPE_K}" \
  --cache-type-v "${CACHE_TYPE_V}" \
  --port "${PORT}" \
  --api-key "${AUTH_KEY}"
