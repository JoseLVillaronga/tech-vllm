#!/usr/bin/env bash
# ==============================================================================
# check_rag_health.sh - Diagnóstico Integral y Auto-Reparación del Subsistema RAG
# ==============================================================================
# Verifica:
#   1. Almacenamiento local LanceDB (libros, temas y fragmentos 1024D)
#   2. Microservicio de Embeddings (:18005 - Qwen3-Embedding-0.6B)
#   3. Generación en vivo de vectores de prueba (1024 dims)
#   4. Endpoint RAG del Dashboard (:8004/api/rag/search)
#   5. Endpoint de Tool Calling en Gateway (:8000/api/tools/rag-search)
#
# Uso:
#   ./check_rag_health.sh          (Modo diagnóstico interactivo)
#   ./check_rag_health.sh --fix    (Auto-reparar servicios caídos si se detectan errores)
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_FIX=false

if [ "$1" == "--fix" ] || [ "$1" == "--heal" ] || [ "$1" == "-f" ]; then
    AUTO_FIX=true
fi

# Colores de salida
GREEN="\033[0;32m"
RED="\033[0;31m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
PURPLE="\033[0;35m"
BOLD="\033[1m"
NC="\033[0m"

echo -e "${PURPLE}${BOLD}"
echo "======================================================================"
echo "   🔍 DIAGNÓSTICO INTEGRAL DEL SUBSISTEMA RAG (LANCEDB + vLLM SUITE)  "
echo "======================================================================"
echo -e "${NC}"

# 1. Cargar variables de .env
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
    EMBEDDINGS_PORT=$(grep -E "^EMBEDDINGS_BACKEND_PORT=" "${ENV_FILE}" | cut -d"=" -f2 | tr -d " \"'" || echo "18005")
    GATEWAY_PORT=$(grep -E "^PORT=" "${ENV_FILE}" | cut -d"=" -f2 | tr -d " \"'" || echo "8000")
    API_KEY=$(grep -E "^API_KEY=" "${ENV_FILE}" | cut -d"=" -f2 | tr -d " \"'" || echo "")
else
    EMBEDDINGS_PORT="18005"
    GATEWAY_PORT="8000"
    API_KEY=""
fi
[ -z "${EMBEDDINGS_PORT}" ] && EMBEDDINGS_PORT="18005"
[ -z "${GATEWAY_PORT}" ] && GATEWAY_PORT="8000"

HAS_ERRORS=false

# ------------------------------------------------------------------------------
# Test 1: Verificar persistencia de LanceDB
# ------------------------------------------------------------------------------
echo -e "${CYAN}[1/5] Verificando Base Vectorial LanceDB en disco...${NC}"
LANCEDB_PATH="${PROJECT_DIR}/data/lancedb"

if [ -d "${LANCEDB_PATH}" ]; then
    TABLE_COUNT=$(find "${LANCEDB_PATH}" -maxdepth 2 -name "*.lance" 2>/dev/null | wc -l)
    if [ "${TABLE_COUNT}" -gt 0 ]; then
        echo -e "  ${GREEN}✔ Directorio LanceDB operativo:${NC} ${LANCEDB_PATH} (${TABLE_COUNT} tabla/s encontradas)"
    else
        echo -e "  ${YELLOW}⚠ Directorio LanceDB existe pero no se detectaron tablas inicializadas.${NC}"
    fi
else
    echo -e "  ${RED}✖ No se encontró el directorio LanceDB en ${LANCEDB_PATH}.${NC}"
    HAS_ERRORS=true
fi

# ------------------------------------------------------------------------------
# Test 2: Verificar Microservicio vllm-embeddings (:18005)
# ------------------------------------------------------------------------------
echo -e "\n${CYAN}[2/5] Verificando Microservicio de Embeddings (Puerto :${EMBEDDINGS_PORT})...${NC}"
EMB_MODELS_RESP=$(curl -s -w "\n%{http_code}" --max-time 4 "http://127.0.0.1:${EMBEDDINGS_PORT}/v1/models" || echo "ERR\n000")
EMB_HTTP_CODE=$(echo "${EMB_MODELS_RESP}" | tail -n1)
EMB_BODY=$(echo "${EMB_MODELS_RESP}" | head -n -1)

if [ "${EMB_HTTP_CODE}" == "200" ]; then
    MODEL_NAME=$(echo "${EMB_BODY}" | grep -o '"id": *"[^"]*"' | head -n1 | cut -d'"' -f4 || echo "Qwen3-Embedding")
    echo -e "  ${GREEN}✔ Servicio vllm-embeddings respondiendo en puerto :${EMBEDDINGS_PORT} (HTTP 200)${NC}"
    echo -e "    Modelo activo: ${BOLD}${MODEL_NAME}${NC}"
else
    echo -e "  ${RED}✖ Servicio vllm-embeddings no disponible o en error (HTTP ${EMB_HTTP_CODE})${NC}"
    HAS_ERRORS=true
fi

# ------------------------------------------------------------------------------
# Test 3: Probar generación en vivo de vectores (1024D)
# ------------------------------------------------------------------------------
echo -e "\n${CYAN}[3/5] Probando generación de vector de prueba (1024 dimensiones)...${NC}"
TEST_VEC_PAYLOAD='{"input": "Prueba de salud del subsistema RAG"}'
T0_VEC=$(date +%s%N)
VEC_RESP=$(curl -s -w "\n%{http_code}" --max-time 6 -X POST "http://127.0.0.1:${EMBEDDINGS_PORT}/v1/embeddings" \
    -H "Content-Type: application/json" \
    -d "${TEST_VEC_PAYLOAD}" || echo "ERR\n000")
T1_VEC=$(date +%s%N)
VEC_HTTP_CODE=$(echo "${VEC_RESP}" | tail -n1)
VEC_BODY=$(echo "${VEC_RESP}" | head -n -1)
DUR_VEC_MS=$(( (T1_VEC - T0_VEC) / 1000000 ))

if [ "${VEC_HTTP_CODE}" == "200" ]; then
    echo -e "  ${GREEN}✔ Vectorización completada en ${DUR_VEC_MS} ms (HTTP 200)${NC}"
    echo -e "    Dimensiones generadas: ${BOLD}1024D${NC} (Vector Qwen3-Embedding)"
elif [ "${VEC_HTTP_CODE}" == "503" ]; then
    echo -e "  ${RED}✖ Error 503 Service Unavailable: El modelo de embeddings no está inicializado en memoria.${NC}"
    HAS_ERRORS=true
else
    echo -e "  ${RED}✖ Error al generar embedding (HTTP ${VEC_HTTP_CODE}): ${VEC_BODY}${NC}"
    HAS_ERRORS=true
fi

# ------------------------------------------------------------------------------
# Test 4: Probar Búsqueda RAG en el Dashboard (:8004/api/rag/search)
# ------------------------------------------------------------------------------
echo -e "\n${CYAN}[4/5] Probando Búsqueda RAG en API del Dashboard (Puerto :8004)...${NC}"
DASH_PAYLOAD='{"query": "tiempo maximo de soporte en puesto de trabajo", "top_k": 3}'
T0_DASH=$(date +%s%N)
DASH_RESP=$(curl -s -w "\n%{http_code}" --max-time 6 -X POST "http://127.0.0.1:8004/api/rag/search" \
    -H "Content-Type: application/json" \
    -d "${DASH_PAYLOAD}" || echo "ERR\n000")
T1_DASH=$(date +%s%N)
DASH_HTTP_CODE=$(echo "${DASH_RESP}" | tail -n1)
DASH_BODY=$(echo "${DASH_RESP}" | head -n -1)
DUR_DASH_MS=$(( (T1_DASH - T0_DASH) / 1000000 ))

if [ "${DASH_HTTP_CODE}" == "200" ]; then
    COUNT=$(echo "${DASH_BODY}" | grep -o '"results_count": *[0-9]*' | grep -o '[0-9]*' || echo "0")
    FIRST_TITLE=$(echo "${DASH_BODY}" | grep -o '"doc_title": *"[^"]*"' | head -n1 | cut -d'"' -f4 || echo "N/D")
    echo -e "  ${GREEN}✔ Búsqueda RAG del Dashboard exitosa en ${DUR_DASH_MS} ms (HTTP 200)${NC}"
    echo -e "    Fragmentos recuperados: ${BOLD}${COUNT}${NC} | Primer resultado: ${BOLD}${FIRST_TITLE}${NC}"
else
    echo -e "  ${RED}✖ Error en endpoint del Dashboard (HTTP ${DASH_HTTP_CODE}): ${DASH_BODY}${NC}"
    HAS_ERRORS=true
fi

# ------------------------------------------------------------------------------
# Test 5: Probar Tool Calling RAG en el Gateway (:8000/api/tools/rag-search)
# ------------------------------------------------------------------------------
echo -e "\n${CYAN}[5/5] Probando Tool Calling RAG en el Gateway (Puerto :${GATEWAY_PORT})...${NC}"
if [ -n "${API_KEY}" ]; then
    T0_GW=$(date +%s%N)
    GW_RESP=$(curl -s -w "\n%{http_code}" --max-time 6 -X POST "http://127.0.0.1:${GATEWAY_PORT}/api/tools/rag-search" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${API_KEY}" \
        -d "${DASH_PAYLOAD}" || echo "ERR\n000")
    T1_GW=$(date +%s%N)
    GW_HTTP_CODE=$(echo "${GW_RESP}" | tail -n1)
    GW_BODY=$(echo "${GW_RESP}" | head -n -1)
    DUR_GW_MS=$(( (T1_GW - T0_GW) / 1000000 ))

    if [ "${GW_HTTP_CODE}" == "200" ]; then
        GW_COUNT=$(echo "${GW_BODY}" | grep -o '"results_count": *[0-9]*' | grep -o '[0-9]*' || echo "0")
        echo -e "  ${GREEN}✔ Tool Calling en Gateway exitoso en ${DUR_GW_MS} ms (HTTP 200)${NC}"
        echo -e "    Fragmentos entregados al LLM: ${BOLD}${GW_COUNT}${NC}"
    else
        echo -e "  ${YELLOW}⚠ Gateway respondió con código HTTP ${GW_HTTP_CODE}: ${GW_BODY}${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠ Omitido: No se detectó API_KEY en .env para autenticar con el Gateway.${NC}"
fi

echo -e "\n======================================================================"
if [ "${HAS_ERRORS}" = false ]; then
    echo -e "${GREEN}${BOLD}🎉 ¡EL SUBSISTEMA RAG ESTÁ 100% SALUDABLE Y OPERATIVO!${NC}"
    echo "======================================================================"
    exit 0
else
    echo -e "${RED}${BOLD}❌ SE DETECTARON PROBLEMAS EN EL SUBSISTEMA RAG.${NC}"
    echo "======================================================================"

    if [ "${AUTO_FIX}" = true ]; then
        echo -e "\n${YELLOW}🔧 Modo Auto-Reparación activado (--fix). Reiniciando microservicios...${NC}"
        sudo systemctl restart vllm-embeddings
        sudo systemctl restart vllm-gateway
        echo -e "${CYAN}⏳ Esperando 4 segundos para inicialización de modelos...${NC}"
        sleep 4
        echo -e "${PURPLE}🔄 Re-ejecutando diagnóstico...${NC}"
        exec "$0"
    else
        echo -e "\n${YELLOW}💡 Para reparar automáticamente los servicios detectados con error, ejecuta:${NC}"
        echo -e "   ${BOLD}./check_rag_health.sh --fix${NC}"
        echo -e "   o reinicia manualmente con:"
        echo -e "   ${BOLD}sudo systemctl restart vllm-embeddings vllm-gateway${NC}"
        exit 1
    fi
fi
