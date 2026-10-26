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
if [ -z "${LLAMA_DIR}" ]; then
    RESOLVED_LLAMA_DIR="${USER_HOME}/llama.cpp"
else
    RESOLVED_LLAMA_DIR="${LLAMA_DIR/\$HOME/$USER_HOME}"
    RESOLVED_LLAMA_DIR="${RESOLVED_LLAMA_DIR/#\/root/$USER_HOME}"
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
if [ ! -f "${MODEL_PATH}" ] && [ -f "${USER_HOME}/llama.cpp/models/$(basename "${MODEL_PATH}")" ]; then
    MODEL_PATH="${USER_HOME}/llama.cpp/models/$(basename "${MODEL_PATH}")"
fi

if [ ! -f "${MODEL_PATH}" ]; then
    echo "❌ Error: No se encontró el archivo del modelo evaluador en ${MODEL_PATH}" >&2
    exit 1
fi

# 5. Detección Dinámica de Arquitectura y Parámetros
PORT="${EVALUATOR_BACKEND_PORT:-${EVALUATOR_PORT:-18300}}"
AUTH_KEY="${API_KEY:-}"

LOWER_MODEL="$(echo "${MODEL_PATH}" | tr '[:upper:]' '[:lower:]')"
if [[ "${LOWER_MODEL}" == *"rwkv"* || "${LOWER_MODEL}" == *"finch"* ]]; then
    IS_RWKV=true
    DEFAULT_ALIAS="v6-Finch-7B-HF-Q5_K_M"
    DEFAULT_CTX=32768
    DEFAULT_LAYERS=99
    ARCH_INFO="RWKV-6 Finch (Modo Booleano CRAG de Latencia Cero, 1M Contexto O(1))"
else
    IS_RWKV=false
    DEFAULT_ALIAS="twil-lm3-q4_k_m"
    DEFAULT_CTX=8192
    DEFAULT_LAYERS=99
    ARCH_INFO="twil-lm3 (SmolLM3 3.1B Fine-Tune Lógica Deductiva JSON)"
fi

ALIAS="${EVALUATOR_ALIAS:-${DEFAULT_ALIAS}}"
CTX_SIZE="${EVALUATOR_CTX_SIZE:-${DEFAULT_CTX}}"
BATCH_SIZE="${EVALUATOR_BATCH_SIZE:-2048}"
UBATCH_SIZE="${EVALUATOR_UBATCH_SIZE:-512}"
GPU_LAYERS="${EVALUATOR_GPU_LAYERS:-${DEFAULT_LAYERS}}"
THREADS="${EVALUATOR_THREADS:-8}"
PARALLEL="${EVALUATOR_PARALLEL:-1}"
CACHE_TYPE_K="${EVALUATOR_CACHE_TYPE_K:-q4_0}"
CACHE_TYPE_V="${EVALUATOR_CACHE_TYPE_V:-q4_0}"

echo "============================================================"
echo "⚖️ Iniciando Microservicio Evaluador de Suficiencia RAG (CRAG)"
echo "============================================================"
echo "👤 Usuario Ejecutor: $(whoami) (Directorio Base: ${USER_HOME})"
echo "📍 Binario:          ${LLAMA_BIN}"
echo "📦 Modelo:           ${MODEL_PATH}"
echo "🧠 Arquitectura:     ${ARCH_INFO}"
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

# Warmup asíncrono en segundo plano: precalienta kernels CUDA al iniciar
(
  max_wait=60
  waited=0
  until curl -s -f "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 || [ $waited -ge $max_wait ]; do
    sleep 1
    waited=$((waited + 1))
  done

  if [ $waited -lt $max_wait ]; then
    AUTH_HEADER=()
    if [ -n "${AUTH_KEY}" ]; then
      AUTH_HEADER=(-H "Authorization: Bearer ${AUTH_KEY}")
    fi
    if [ "${IS_RWKV}" = true ]; then
      curl -s -X POST "http://127.0.0.1:${PORT}/completion" \
        -H "Content-Type: application/json" \
        "${AUTH_HEADER[@]}" \
        -d '{"prompt": "User: Precalentamiento de kernels CUDA.\n\nAssistant:", "n_predict": 1, "temperature": 0.0}' \
        >/dev/null 2>&1 || true
    else
      curl -s -X POST "http://127.0.0.1:${PORT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        "${AUTH_HEADER[@]}" \
        -d '{"model": "'"${ALIAS}"'", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}' \
        >/dev/null 2>&1 || true
    fi
    echo "🔥 [Evaluator Warmup] Kernels CUDA precalentados exitosamente en :${PORT}"
  fi
) &

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
