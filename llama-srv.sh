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
UBATCH_SIZE="${LLAMA_UBATCH_SIZE:-1024}"
GPU_LAYERS="${LLAMA_GPU_LAYERS:-256}"
REASONING="${LLAMA_REASONING:-off}"
THREADS="${LLAMA_THREADS:-8}"
LOAD_MODE="${LLAMA_LOAD_MODE:-mlock}"
AUTH_KEY="${API_KEY:-}"
PARALLEL="${LLAMA_PARALLEL:-2}"
SLOT_SAVE_PATH="${LLAMA_SLOT_SAVE_PATH:-${PROJECT_DIR}/scratch/slots}"
mkdir -p "${SLOT_SAVE_PATH}"

# 5.1 Parámetro Opcional Multimodal Projector (Visión)
MMPROJ_PATH="${LLAMA_MMPROJ_PATH:-}"
MMPROJ_ARGS=()
if [ -n "${MMPROJ_PATH}" ] && [ -f "${MMPROJ_PATH}" ]; then
    MMPROJ_DESC="${MMPROJ_PATH}"
    MMPROJ_ARGS=(--mmproj "${MMPROJ_PATH}")
else
    MMPROJ_DESC="Desactivado (Solo Texto)"
fi

# 5.2 Parámetros Condicionales por Arquitectura (MoE vs Denso)
IS_MOE="${LLAMA_IS_MOE:-false}"
MOE_ARGS=()
if [ "${IS_MOE}" = "true" ]; then
    ARCH_TYPE="MoE (Mixture of Experts)"
    N_CPU_MOE="${LLAMA_N_CPU_MOE:-0}"
    if [ "${N_CPU_MOE}" -gt 0 ] 2>/dev/null; then
        MOE_ARGS=(--n-cpu-moe "${N_CPU_MOE}")
        MOE_DESC="${N_CPU_MOE} capas de expertos en CPU"
    else
        MOE_DESC="100% en GPU (--n-cpu-moe 0)"
    fi
else
    ARCH_TYPE="Denso (Dense Transformer)"
    MOE_DESC="No aplica (desactivado)"
fi

# 5.3 Cuantización de KV Cache (Optimización de VRAM para grandes contextos)
CACHE_K="${LLAMA_CACHE_TYPE_K:-}"
CACHE_V="${LLAMA_CACHE_TYPE_V:-}"
CACHE_ARGS=()
if [ -n "${CACHE_K}" ] && [ "${CACHE_K}" != "f16" ]; then
    CACHE_ARGS+=(--cache-type-k "${CACHE_K}")
fi
if [ -n "${CACHE_V}" ] && [ "${CACHE_V}" != "f16" ]; then
    CACHE_ARGS+=(--cache-type-v "${CACHE_V}")
fi
KV_CACHE_DESC="K=${CACHE_K:-f16} / V=${CACHE_V:-f16}"

echo "============================================================"
echo "🦙 Iniciando llama-server para vLLM Suite"
echo "============================================================"
echo "👤 Usuario Ejecutor: $(whoami) (Directorio Base: ${USER_HOME})"
echo "📍 Binario:          ${LLAMA_BIN}"
echo "📦 Modelo:           ${MODEL_PATH}"
echo "🏷️ Alias:            ${ALIAS}"
echo "🏗️ Arquitectura:     ${ARCH_TYPE} (MoE: ${MOE_DESC})"
echo "💾 KV Cache:         ${KV_CACHE_DESC}"
echo "👁️ Proyector Visión:  ${MMPROJ_DESC}"
echo "🔌 Puerto Backend:   ${PORT}"
echo "🧠 Contexto Máximo:  ${CTX_SIZE} tokens"
echo "⚡ Batch Lógico:     ${BATCH_SIZE}"
echo "🚀 Micro-Batch (uB): ${UBATCH_SIZE}"
echo "🎮 GPU Layers:       ${GPU_LAYERS}"
echo "💭 Razonamiento:     ${REASONING}"
echo "🔒 Modo de Carga:    --load-mode ${LOAD_MODE}"
echo "🧵 Hilos CPU:        ${THREADS}"
echo "👥 Slots Paralelos:  ${PARALLEL}"
echo "💾 Ruta Slots KV:    ${SLOT_SAVE_PATH}"
echo "============================================================"

# Reemplazar la shell por el proceso llama-server para gestión nativa en systemd
exec "${LLAMA_BIN}" \
  --model "${MODEL_PATH}" \
  --alias "${ALIAS}" \
  "${MMPROJ_ARGS[@]}" \
  "${MOE_ARGS[@]}" \
  "${CACHE_ARGS[@]}" \
  --ctx-size "${CTX_SIZE}" \
  --parallel "${PARALLEL}" \
  --slot-save-path "${SLOT_SAVE_PATH}" \
  --batch-size "${BATCH_SIZE}" \
  --ubatch-size "${UBATCH_SIZE}" \
  --gpu-layers "${GPU_LAYERS}" \
  --reasoning "${REASONING}" \
  --flash-attn on \
  --threads "${THREADS}" \
  --load-mode "${LOAD_MODE}" \
  --port "${PORT}" \
  --api-key "${AUTH_KEY}"
