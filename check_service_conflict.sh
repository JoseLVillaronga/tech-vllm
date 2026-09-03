#!/usr/bin/env bash
# ==============================================================================
# Verificador de Exclusión Mutua para vLLM Suite
# Evita colisiones de VRAM y puertos entre vllm.service y vllm-llama.service
# ==============================================================================
set -e

OPPONENT_SERVICE="$1"
PORT="${2:-18100}"

# 1. Comprobar si el servicio oponente está activo
if [ -n "${OPPONENT_SERVICE}" ] && systemctl is-active --quiet "${OPPONENT_SERVICE}"; then
    echo "❌ Conflicto: El servicio ${OPPONENT_SERVICE} está activo. Deténgalo antes de iniciar." >&2
    exit 1
fi

# 2. Comprobar si el puerto backend ya está ocupado por otro proceso
if [ -n "${PORT}" ] && ss -tulpn | grep -q ":${PORT} "; then
    echo "❌ Conflicto: El puerto backend ${PORT} ya está en uso. Verifique y detenga el proceso que lo ocupa." >&2
    exit 1
fi

exit 0
