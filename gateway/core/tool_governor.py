import os
import sys
import re
from typing import List, Dict, Any, Tuple, Optional
from gateway.core.context_pruner import estimate_tokens


# Configuración Canónica de Presupuesto RAG (con fallbacks y soporte para .env)
DEFAULT_MAX_TOOL_TOKENS = 50000
DEFAULT_MIN_TOOL_TOKENS = 10000
DEFAULT_INSUFFICIENT_TOOL_TOKENS = 5000
DEFAULT_MAX_EXPLORATION_CALLS = 4


def get_max_tool_tokens() -> int:
    """Techo máximo de tokens de herramientas por turno antes de retirar 'tools' (Hard Circuit Breaker)."""
    try:
        return int(os.getenv("GATEWAY_MAX_TOOL_TOKENS", str(DEFAULT_MAX_TOOL_TOKENS)))
    except (ValueError, TypeError):
        return DEFAULT_MAX_TOOL_TOKENS


def get_min_tool_tokens() -> int:
    """Objetivo de evidencia documental para consultas de fondo antes de recomendar síntesis."""
    try:
        return int(os.getenv("GATEWAY_MIN_TOOL_TOKENS", str(DEFAULT_MIN_TOOL_TOKENS)))
    except (ValueError, TypeError):
        return DEFAULT_MIN_TOOL_TOKENS


def get_insufficient_tool_tokens() -> int:
    """Umbral de evidencia mínima. Si tras N llamadas no se alcanza, se declara insuficiencia."""
    try:
        return int(os.getenv("GATEWAY_INSUFFICIENT_TOOL_TOKENS", str(DEFAULT_INSUFFICIENT_TOOL_TOKENS)))
    except (ValueError, TypeError):
        return DEFAULT_INSUFFICIENT_TOOL_TOKENS


def get_max_exploration_calls() -> int:
    """Cantidad de llamadas tras las cuales se evalúa el semáforo de suficiencia."""
    try:
        return int(os.getenv("GATEWAY_MAX_EXPLORATION_CALLS", str(DEFAULT_MAX_EXPLORATION_CALLS)))
    except (ValueError, TypeError):
        return DEFAULT_MAX_EXPLORATION_CALLS


def is_broad_or_deep_query(user_content: str) -> bool:
    """
    Detecta si la consulta del usuario es doctrinal, de catálogo o profunda,
    justificando la recomendación de alcanzar el piso de 10.000 tokens.
    """
    if not user_content or not isinstance(user_content, str):
        return False
    text = user_content.lower()
    patterns = [
        r"\blista\b", r"\btodos\b", r"\btodas\b", r"\btratados?\b", r"\bconvenios?\b",
        r"\bprofundidad\b", r"\bexhaustiv[ao]\b", r"\bcomparativ[ao]\b", r"\bcat[aá]logo\b",
        r"\bdoctrina\b", r"\bcompleto\b", r"\bbiblioteca\b", r"\br[eé]gimen general\b",
        r"\bmarco legal\b", r"\ban[aá]lisis\b"
    ]
    return any(re.search(pat, text) for pat in patterns)


def inspect_active_turn_tools(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Inspecciona los mensajes correspondientes al turno de usuario activo.
    Identifica llamadas a herramientas, tokens acumulados y el índice del último mensaje tool.
    """
    if not messages or not isinstance(messages, list):
        return {
            "tool_call_count": 0,
            "accumulated_tool_tokens": 0,
            "total_turn_tokens": 0,
            "last_tool_idx": -1,
            "user_query": "",
            "is_deep_query": False
        }

    # Encontrar el índice del último mensaje del usuario
    last_user_idx = -1
    user_query = ""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            c = messages[i].get("content", "")
            if isinstance(c, str):
                user_query = c
            elif isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and "text" in part:
                        user_query += " " + str(part.get("text", ""))
            break

    if last_user_idx == -1:
        last_user_idx = 0

    active_turn_msgs = messages[last_user_idx:]
    tool_msgs: List[Dict[str, Any]] = []
    last_tool_idx = -1

    for idx, m in enumerate(messages):
        if idx >= last_user_idx and m.get("role") == "tool":
            tool_msgs.append(m)
            last_tool_idx = idx

    tool_call_count = len(tool_msgs)
    accumulated_tool_tokens = estimate_tokens(tool_msgs) if tool_msgs else 0
    total_turn_tokens = estimate_tokens(active_turn_msgs)

    return {
        "tool_call_count": tool_call_count,
        "accumulated_tool_tokens": accumulated_tool_tokens,
        "total_turn_tokens": total_turn_tokens,
        "last_tool_idx": last_tool_idx,
        "user_query": user_query.strip(),
        "is_deep_query": is_broad_or_deep_query(user_query)
    }


def apply_tool_budget_governor(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Gobernador de Ciclo de Vida y Presupuesto RAG:
    Aplica determinismo matemático sobre las llamadas a herramientas en el turno activo.
    
    Zonas de Decisión:
    1. TECHO MÁXIMO (>= 50.000 tokens):
       - Retira físicamente 'tools' y 'tool_choice' del payload.
       - Inyecta banner de forzado de redacción final.
    2. ZONA DE INSUFICIENCIA (Llamadas >= 4 y Tokens < 5.000):
       - Retira 'tools' y 'tool_choice'.
       - Inyecta directiva de cierre perentorio: "No tengo datos suficientes".
    3. ZONA DISCRECIONAL (Llamadas >= 4 y 5.000 <= Tokens < 10.000):
       - Mantiene 'tools' activas (NO desalienta continuar).
       - Inyecta recordatorio de que puede responder si está satisfecho o seguir explorando a su criterio.
    4. ZONA ÓPTIMA (> 10.000 tokens y < 50.000 tokens):
       - Mantiene 'tools' activas. Evidencia consolidada.
    5. EXPLORACIÓN TEMPRANA (< 4 llamadas y < 10.000 tokens):
       - En consultas de amplitud, recuerda combinar herramientas hacia el objetivo de 10k.
    """
    messages = data.get("messages")
    if not messages or not isinstance(messages, list):
        return data, {"status": "no_messages"}

    stats = inspect_active_turn_tools(messages)
    tool_count = stats["tool_call_count"]
    tool_tokens = stats["accumulated_tool_tokens"]
    last_tool_idx = stats["last_tool_idx"]
    is_deep = stats["is_deep_query"]

    # Si no hubo llamadas a herramientas en este turno, no aplicar modificaciones
    if tool_count == 0 or last_tool_idx == -1:
        return data, {"status": "idle", "tool_count": 0, "tool_tokens": 0}

    max_tokens = get_max_tool_tokens()
    insufficient_tokens = get_insufficient_tool_tokens()
    min_tokens = get_min_tool_tokens()
    max_calls = get_max_exploration_calls()

    banner = ""
    governor_action = "none"

    # 1. ZONA DE TECHO MÁXIMO (Circuit Breaker Duro)
    if tool_tokens >= max_tokens:
        governor_action = "hard_cap"
        data.pop("tools", None)
        data.pop("tool_choice", None)
        banner = (
            f"\n\n🛑 [GOBERNADOR RAG - TECHO DE CONTEXTO ALCANZADO]: "
            f"Se han acumulado ~{tool_tokens:,} tokens de fuentes documentales en esta consulta (límite máximo: {max_tokens:,}). "
            f"El cupo de herramientas queda CERRADO para preservar la estabilidad de la memoria. "
            f"Proceda de inmediato a redactar su respuesta final completa, estructurada y fundada con la evidencia disponible."
        )
        print(
            f"🛑 [Tool Governor] Techo alcanzado: ~{tool_tokens:,} tokens en {tool_count} llamadas. "
            f"Herramientas deshabilitadas para forzar síntesis final.",
            file=sys.stderr,
            flush=True
        )

    # 2. ZONA DE INSUFICIENCIA TRAS 4 LLAMADAS (< 5.000 tokens)
    elif tool_count >= max_calls and tool_tokens < insufficient_tokens:
        governor_action = "insufficient_data_cut"
        data.pop("tools", None)
        data.pop("tool_choice", None)
        banner = (
            f"\n\n⚠️ [GOBERNADOR RAG - FUENTES DOCUMENTALES INSUFICIENTES]: "
            f"Se han completado {tool_count} rondas de búsqueda acumulando solo ~{tool_tokens:,} tokens (< {insufficient_tokens:,}). "
            f"INVARIANTE DE VERACIDAD PERENTORIO: Se corta el bucle de búsqueda y se desalienta continuar. "
            f"Concluya su respuesta declarando formalmente: 'No tengo datos suficientes en las fuentes oficiales de la base documental para responder a esta consulta con certeza.' "
            f"Queda ESTRICTAMENTE PROHIBIDO inferir o responder desde la memoria paramétrica."
        )
        print(
            f"⚠️ [Tool Governor] Insuficiencia detectada: {tool_count} llamadas con solo ~{tool_tokens:,} tokens. "
            f"Herramientas deshabilitadas para forzar declaración honesta de falta de fuentes.",
            file=sys.stderr,
            flush=True
        )

    # 3. ZONA DISCRECIONAL TRAS 4 LLAMADAS (5.000 a 10.000 tokens)
    elif tool_count >= max_calls and tool_tokens < min_tokens:
        governor_action = "discretionary_zone"
        # NO se deshabilitan las herramientas. El LLM decide si continuar o responder.
        banner = (
            f"\n\nℹ️ [GOBERNADOR RAG - ZONA DISCRECIONAL]: "
            f"Se han completado {tool_count} rondas de búsqueda con ~{tool_tokens:,} tokens acumulados. "
            f"Si considera que la evidencia recopilada es suficiente para contestar con rigor, puede proceder a redactar su respuesta fundamentada. "
            f"Si restan aspectos relevantes por verificar, puede continuar haciendo llamadas a herramientas a su propio criterio hasta alcanzar el techo documental."
        )

    # 4. ZONA ÓPTIMA (> 10.000 tokens y < 50.000 tokens)
    elif tool_tokens >= min_tokens:
        governor_action = "healthy_zone"
        # Herramientas habilitadas. Evidencia suficiente.
        banner = (
            f"\n\n✅ [GOBERNADOR RAG - EVIDENCIA ROBUSTA]: "
            f"~{tool_tokens:,} tokens de fuentes oficiales acumulados en este turno. "
            f"Proceda a redactar su fundamentación completa cuando la evidencia sea suficiente, o continúe explorando si restan puntos específicos."
        )

    # 5. EXPLORACIÓN TEMPRANA (< 4 llamadas y < 10.000 tokens)
    elif is_deep and tool_count < max_calls:
        governor_action = "early_deep_guidance"
        banner = (
            f"\n\n💡 [GOBERNADOR RAG]: "
            f"Evidencia preliminar: ~{tool_tokens:,} tokens en {tool_count} llamada(s). "
            f"Para consultas de fondo, catálogos, tratados o marcos legales amplios, utiliza 'obtener_indice_biblioteca' para mapear las obras pertinentes y combina herramientas jerárquicas "
            f"('obtener_estructura_documento' y 'leer_documento_completo') hacia el objetivo de ~{min_tokens:,} tokens. "
            f"No sintetice prematuramente con un único fragmento aislado si la consulta requiere exhaustividad o catálogo."
        )

    # Inyectar el banner en el último mensaje 'tool' si se definió una directiva
    if banner and 0 <= last_tool_idx < len(messages):
        last_m = dict(messages[last_tool_idx])
        curr_content = last_m.get("content", "")
        if isinstance(curr_content, str):
            # Evitar inyecciones duplicadas si el payload pasa varias veces por enriquecimiento
            if "[GOBERNADOR RAG" not in curr_content:
                last_m["content"] = curr_content + banner
                messages[last_tool_idx] = last_m

    return data, {
        "status": "applied",
        "action": governor_action,
        "tool_call_count": tool_count,
        "accumulated_tool_tokens": tool_tokens,
        "tools_disabled": "tools" not in data
    }
