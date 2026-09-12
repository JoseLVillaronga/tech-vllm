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
            f"Queda ESTRICTAMENTE PROHIBIDO emitir etiquetas '<tool_call>', JSON de funciones o simular consultas adicionales. "
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
            f"Queda ESTRICTAMENTE PROHIBIDO inferir o responder desde la memoria paramétrica o emitir etiquetas '<tool_call>'."
        )
        print(
            f"⚠️ [Tool Governor] Insuficiencia detectada: {tool_count} llamadas con solo ~{tool_tokens:,} tokens. "
            f"Herramientas deshabilitadas para forzar declaración honesta de falta de fuentes.",
            file=sys.stderr,
            flush=True
        )

    # Si las herramientas quedan deshabilitadas (hard cap o insuficiencia),
    # levantar la directiva perentoria de llamar a tools del mensaje del usuario
    # para evitar contradicciones y eliminar la emisión de etiquetas <tool_call> en texto
    if governor_action in ["hard_cap", "insufficient_data_cut"]:
        for m in reversed(messages):
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, str) and "[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO" in c:
                    base_txt = re.split(r"\n\n\[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", c)[0].strip()
                    if governor_action == "hard_cap":
                        closure_directive = (
                            "\n\n[FASE DE INVESTIGACIÓN CONCLUIDA - SÍNTESIS FINAL OBLIGATORIA (MEA)]:\n"
                            f"La fase de recuperación documental ha concluido habiendo alcanzado el techo de evidencia (~{tool_tokens:,} tokens). "
                            "Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas. "
                            "Tu objetivo prioritario y excluyente ahora es redactar tu respuesta final completa, fundamentada y estructurada en texto natural, basándote en las fuentes oficiales recopiladas. "
                            "Está ESTRICTAMENTE PROHIBIDO emitir etiquetas '<tool_call>', funciones simuladas o postergar la respuesta: redacta tu conclusión definitiva de inmediato."
                        )
                    else:
                        closure_directive = (
                            "\n\n[FASE DE INVESTIGACIÓN CONCLUIDA - INSUFICIENCIA DE FUENTES (MEA)]:\n"
                            f"Se han completado {tool_count} rondas de búsqueda con evidencia insuficiente (< {insufficient_tokens:,} tokens). "
                            "Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas. "
                            "Conforme al Invariante de Veracidad, redacta tu respuesta declarando formalmente la falta de fuentes suficientes sin inventar datos de memoria paramétrica ni emitir etiquetas '<tool_call>'."
                        )
                    m["content"] = f"{base_txt}{closure_directive}"
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get("type") == "text":
                            ptxt = part.get("text", "")
                            if "[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO" in ptxt:
                                base_txt = re.split(r"\n\n\[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", ptxt)[0].strip()
                                closure_directive = (
                                    "\n\n[FASE DE INVESTIGACIÓN CONCLUIDA - SÍNTESIS FINAL OBLIGATORIA (MEA)]:\n"
                                    f"La fase de recuperación documental ha concluido habiendo alcanzado el techo de evidencia (~{tool_tokens:,} tokens). "
                                    "Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas. "
                                    "Redacta de inmediato tu respuesta final en texto estructurado basándote en las fuentes oficiales recopiladas. "
                                    "Está ESTRICTAMENTE PROHIBIDO emitir etiquetas '<tool_call>'."
                                )
                                part["text"] = f"{base_txt}{closure_directive}"
                break

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


def parse_raw_tool_calls(text: str, valid_tools: set) -> Optional[List[Dict[str, Any]]]:
    """
    Auto-guardia de Fallback para Modelos Locales (Mistral / Nemo / DeepSeek):
    Detecta si el contenido generado en 'content' es en realidad una llamada a herramienta
    en formato de array JSON o pseudo-tokens sin interceptar por el parser nativo de llama-server:
    1. Formato Array JSON: [{"name": "...", "arguments": {...}}] o [{"function": ...}]
    2. Formato Tokens Corchete: [func_name[CALL_ID]...[ARGS]...]
    
    Retorna una lista de tool_calls formales compatibles con OpenAI o None si es texto regular.
    """
    import json
    import uuid
    import re

    if not text or not valid_tools:
        return None

    cleaned = text.strip()
    if not cleaned.startswith("["):
        return None

    # Caso 1: Array JSON [{"name": ...}]
    if cleaned.endswith("]"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) > 0:
                calls = []
                for idx, item in enumerate(parsed):
                    if not isinstance(item, dict):
                        return None
                    fn_name = item.get("name")
                    args = item.get("arguments")
                    if not fn_name and "function" in item and isinstance(item["function"], dict):
                        fn_name = item["function"].get("name")
                        args = item["function"].get("arguments")

                    if fn_name and fn_name in valid_tools:
                        cid = item.get("id") or item.get("call_id") or f"call_{uuid.uuid4().hex[:8]}"
                        if isinstance(args, dict):
                            args_str = json.dumps(args, ensure_ascii=False)
                        elif isinstance(args, str):
                            args_str = args
                        else:
                            args_str = "{}"
                        calls.append({
                            "index": idx,
                            "id": str(cid),
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": args_str
                            }
                        })
                if calls:
                    return calls
        except Exception:
            pass

    # Caso 2: Tokens delimitadores entre corchetes [func[CALL_ID]...[ARGS]...]
    if cleaned.startswith("[") and ("[ARGS]" in cleaned or "[CALL_ID]" in cleaned):
        m = re.match(r"^\[([a-zA-Z0-9_\-]+)(?:\[CALL_ID\]([^\[\]]+))?\[ARGS\](.*)\]$", cleaned, re.DOTALL)
        if m:
            fn_name = m.group(1).strip()
            cid = (m.group(2) or "").strip() or f"call_{uuid.uuid4().hex[:8]}"
            args_str = (m.group(3) or "").strip()
            if fn_name in valid_tools:
                try:
                    json.loads(args_str)
                    return [{
                        "index": 0,
                        "id": str(cid),
                        "type": "function",
                        "function": {
                            "name": fn_name,
                            "arguments": args_str
                        }
                    }]
                except Exception:
                    pass

    return None

