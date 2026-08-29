#!/usr/bin/env bash
# ==============================================================================
# Orquestador de Sincronización RAG con Gestión Segura de VRAM
# Proyecto: vLLM Suite - Teccam Knowledge Base
#
# Comportamiento:
# 1. Detecta si el servicio del LLM (vllm.service) está activo.
# 2. Si está activo, lo detiene temporalmente para liberar los ~14 GB de VRAM en la RTX 3090.
# 3. Verifica que la VRAM disponible sea segura (< 10 GB en uso).
# 4. Ejecuta la sincronización en CUDA a máxima aceleración (~60 a 90 segundos).
# 5. Reinicia DE FORMA GARANTIZADA (trap EXIT) el servicio vllm.service al terminar.
# ==============================================================================

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"
SYNC_SCRIPT="${PROJECT_DIR}/app_rag_sync.py"
LLM_SERVICE="vllm.service"

echo "======================================================================"
echo "🔄 [RAG Scheduled Orchestrator] Iniciando ciclo de sincronización..."
echo "⏰ Fecha / Hora: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

WAS_LLM_RUNNING=false

# Función de limpieza y restauración garantizada
cleanup() {
    local exit_code=$?
    echo ""
    echo "======================================================================"
    if [ "${WAS_LLM_RUNNING}" = true ]; then
        echo "🚀 [RAG Scheduled Orchestrator] Restaurando servicio principal del LLM (${LLM_SERVICE})..."
        systemctl start "${LLM_SERVICE}" || echo "⚠️ Advertencia: No se pudo iniciar ${LLM_SERVICE} automáticamente."
        
        # Esperar confirmación de arranque
        for i in {1..15}; do
            if systemctl is-active --quiet "${LLM_SERVICE}"; then
                echo "✅ [RAG Scheduled Orchestrator] ${LLM_SERVICE} está activo y respondiendo."
                break
            fi
            sleep 1
        done
    fi
    
    if [ ${exit_code} -eq 0 ]; then
        echo "🎉 [RAG Scheduled Orchestrator] Ciclo de sincronización completado exitosamente."
    else
        echo "❌ [RAG Scheduled Orchestrator] El ciclo terminó con código de error ${exit_code}."
    fi
    echo "⏰ Fin: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================================================================"
    exit ${exit_code}
}

trap cleanup EXIT INT TERM

# 1. Comprobar si el LLM está corriendo
if systemctl is-active --quiet "${LLM_SERVICE}"; then
    WAS_LLM_RUNNING=true
    echo "🛑 [RAG Scheduled Orchestrator] Deteniendo ${LLM_SERVICE} para liberar VRAM..."
    systemctl stop "${LLM_SERVICE}"
    
    # Esperar hasta 20 segundos para que libere completamente la memoria GPU
    for i in {1..20}; do
        if ! systemctl is-active --quiet "${LLM_SERVICE}"; then
            echo "   ✔ ${LLM_SERVICE} detenido correctamente."
            break
        fi
        sleep 1
    done
    sleep 2
else
    echo "ℹ️ [RAG Scheduled Orchestrator] ${LLM_SERVICE} no estaba activo. Omitiendo detención."
fi

# 2. Verificar consumo de VRAM en GPU 0
if command -v nvidia-smi &> /dev/null; then
    VRAM_USED_MB=$(nvidia-smi --id=0 --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | tr -d ' ' || echo "0")
    echo "📊 [RAG Scheduled Orchestrator] VRAM en uso en GPU 0: ${VRAM_USED_MB} MB"
    
    if [ "${VRAM_USED_MB}" -gt 10240 ]; then
        echo "⚠️ [RAG Scheduled Orchestrator] Advertencia: El uso de VRAM (${VRAM_USED_MB} MB) supera los 10 GB."
        echo "   Esperando 5 segundos adicionales..."
        sleep 5
    fi
fi

# 3. Ejecutar sincronizador Teccam -> LanceDB con aceleración CUDA
echo "⚡ [RAG Scheduled Orchestrator] Ejecutando app_rag_sync.py..."
"${VENV_PYTHON}" "${SYNC_SCRIPT}" "$@"
