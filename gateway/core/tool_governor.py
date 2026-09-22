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
DEFAULT_MAX_TOOL_CALLS_PER_TURN = 7

try:
    from rag.evaluator import evaluate_context_sufficiency
except Exception:
    evaluate_context_sufficiency = None


def get_max_tool_calls_per_turn() -> int:
    """Límite absoluto de llamadas a herramientas por turno antes de retirar 'tools' (Hard Circuit Breaker)."""
    try:
        return int(os.getenv("GATEWAY_MAX_TOOL_CALLS_PER_TURN", str(DEFAULT_MAX_TOOL_CALLS_PER_TURN)))
    except (ValueError, TypeError):
        return DEFAULT_MAX_TOOL_CALLS_PER_TURN


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

    # Deduplicación perimetral de llamadas y resultados idénticos en el turno activo
    last_user_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break
    if last_user_idx == -1:
        last_user_idx = 0

    last_assistant_with_tools_idx = -1
    for i in range(len(messages) - 1, last_user_idx - 1, -1):
        if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
            last_assistant_with_tools_idx = i
            break

    if last_assistant_with_tools_idx != -1:
        ast_msg = messages[last_assistant_with_tools_idx]
        raw_tcs = ast_msg.get("tool_calls", [])
        if isinstance(raw_tcs, list) and len(raw_tcs) > 1:
            deduped_tcs, dups = deduplicate_tool_calls(raw_tcs)
            if dups > 0:
                ast_msg["tool_calls"] = deduped_tcs
                kept_tool_ids = {tc.get("id") for tc in deduped_tcs if tc.get("id")}
                filtered_msgs = []
                for idx, m in enumerate(messages):
                    if idx > last_assistant_with_tools_idx and m.get("role") == "tool":
                        tid = m.get("tool_call_id")
                        if tid and tid not in kept_tool_ids:
                            continue
                    filtered_msgs.append(m)
                messages = filtered_msgs
                data["messages"] = messages
                print(f"🧹 [Tool Governor] Pruning de {dups} llamada/s y resultado/s duplicados en el turno activo antes de enviar al modelo.", flush=True)

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
    max_calls = get_max_tool_calls_per_turn()
    user_query = stats.get("user_query", "")

    # Recopilar evidencia documental acumulada en el turno activo para evaluación
    active_tool_contents = [
        str(m.get("content", "")) for idx, m in enumerate(messages)
        if idx >= last_user_idx and m.get("role") == "tool"
    ]
    combined_tool_text = "\n\n".join(active_tool_contents)

    # Evaluar suficiencia documental lógica (CRAG)
    eval_result = {"suficiente": True, "motivo": "", "faltantes": [], "evaluador": "none"}
    if evaluate_context_sufficiency and user_query and combined_tool_text:
        try:
            eval_result = evaluate_context_sufficiency(user_query, combined_tool_text)
        except Exception as eval_err:
            print(f"⚠️ [Tool Governor] Error evaluando suficiencia: {eval_err}", file=sys.stderr, flush=True)
            eval_result = {"suficiente": True, "motivo": "Excepción en evaluador", "faltantes": [], "evaluador": "error"}

    is_sufficient = eval_result.get("suficiente", True)
    eval_reason = eval_result.get("motivo", "")

    banner = ""
    governor_action = "none"

    # 1. ZONA DE TECHO MÁXIMO DE TOKENS (Circuit Breaker Duro 50k)
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

    # 2. ZONA DE LÍMITE MÁXIMO DE CONSULTAS (Circuit Breaker Duro 7 Llamadas)
    elif tool_count >= max_calls:
        data.pop("tools", None)
        data.pop("tool_choice", None)
        if not is_sufficient:
            governor_action = "max_calls_abstention"
            banner = (
                f"\n\n⚠️ [GOBERNADOR RAG - LÍMITE DE CONSULTAS ALCANZADO (ABSTENCIÓN MEA)]:\n"
                f"Se ha alcanzado el límite de {tool_count} consultas a herramientas sin hallar evidencia suficiente en las fuentes oficiales ({eval_reason}).\n"
                f"INVARIANTE DE VERACIDAD PERENTORIO: El cupo de herramientas queda CERRADO. Concluya su respuesta declarando formalmente: "
                f"'No tengo datos suficientes en las fuentes oficiales de la base documental para responder a esta consulta con certeza.'\n"
                f"Queda ESTRICTAMENTE PROHIBIDO inferir o responder desde la memoria paramétrica o emitir etiquetas '<tool_call>'."
            )
            print(
                f"⚠️ [Tool Governor] Límite de {tool_count} llamadas alcanzado con evidencia insuficiente. "
                f"Herramientas deshabilitadas para forzar abstención honesta.",
                file=sys.stderr,
                flush=True
            )
        else:
            governor_action = "max_calls_synthesis"
            banner = (
                f"\n\n🛑 [GOBERNADOR RAG - LÍMITE DE CONSULTAS ALCANZADO]:\n"
                f"Se ha completado el límite de {tool_count} consultas a herramientas habiendo obtenido evidencia suficiente ({eval_reason}).\n"
                f"El cupo de herramientas queda CERRADO. Proceda de inmediato a redactar su respuesta final completa, estructurada y fundada con la evidencia disponible.\n"
                f"Queda ESTRICTAMENTE PROHIBIDO emitir etiquetas '<tool_call>'."
            )
            print(
                f"🛑 [Tool Governor] Límite de {tool_count} llamadas alcanzado con evidencia suficiente. "
                f"Herramientas deshabilitadas para forzar síntesis final.",
                file=sys.stderr,
                flush=True
            )

    # 3. ZONA ÓPTIMA POR VOLUMEN DOCUMENTAL (>= 10.000 tokens)
    elif tool_tokens >= min_tokens:
        governor_action = "healthy_zone"
        banner = (
            f"\n\n✅ [GOBERNADOR RAG - EVIDENCIA ROBUSTA]: "
            f"~{tool_tokens:,} tokens de fuentes oficiales acumulados en este turno. "
            f"Proceda a redactar su fundamentación completa cuando la evidencia sea suficiente, o continúe explorando si restan puntos específicos."
        )

    # 4. GOBERNANZA CONDICIONAL UNIVERSAL (Datos insuficientes tras búsqueda)
    elif not is_sufficient:
        governor_action = "conditional_insufficient"
        # Herramientas PERMANECEN ACTIVAS. El LLM decide si profundizar o abstenerse.
        banner = (
            f"\n\n⚠️ [DICTAMEN RAG - CONDICIÓN DE SUFICIENCIA]:\n"
            f"Los datos recuperados hasta este momento son INSUFICIENTES para responder de manera concluyente y verídica a la consulta del usuario ({eval_reason}).\n"
            f"1. SI Y SOLO SI vas a contestar definitivamente ahora sin realizar más consultas: DEBES ABSTENERTE y declarar formalmente: 'No tengo datos suficientes en las fuentes oficiales de la base documental para responder a esta consulta con certeza.'\n"
            f"2. SI CONSIDERAS NECESARIO PROFUNDIZAR: dispones de herramientas para buscar términos más específicos, navegar la estructura o consultar otros documentos oficiales (Ronda {tool_count}/{max_calls})."
        )
        if is_deep and tool_count < 2:
            banner += (
                f"\n💡 [Guía de Amplitud]: Para consultas de catálogo, tratados o marcos legales amplios, "
                f"utiliza 'obtener_indice_biblioteca' para mapear las obras pertinentes y 'leer_documento_completo'."
            )

    # 5. EVIDENCIA SUFICIENTE EN CONSULTA PUNTUAL (< 10.000 tokens)
    else:
        governor_action = "sufficient_ready"
        banner = (
            f"\n\n✅ [GOBERNADOR RAG - EVIDENCIA SUFICIENTE]: "
            f"La evidencia recopilada satisface la consulta ({eval_reason}). "
            f"Proceda a redactar su respuesta fundada o continúe consultando herramientas a su propio criterio si requiere mayor amplitud."
        )

    # Cuando ya hubo llamadas a herramientas en el turno activo (tool_count > 0),
    # levantar la directiva perentoria de "tu primer token DEBE ser una herramienta"
    # para evitar bucles ciegos de etiquetas <tool_call> y permitir que el modelo sintetice o se abstenga
    if tool_count > 0:
        for m in reversed(messages):
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, str) and "[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO" in c:
                    base_txt = re.split(r"\n\n\[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", c)[0].strip()
                    if governor_action in ["hard_cap", "max_calls_synthesis"]:
                        closure_directive = (
                            "\n\n[FASE DE INVESTIGACIÓN CONCLUIDA - SÍNTESIS FINAL OBLIGATORIA (MEA)]:\n"
                            f"La fase de recuperación documental ha concluido (~{tool_tokens:,} tokens en {tool_count} llamada/s). "
                            "Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas. "
                            "Tu objetivo prioritario y excluyente ahora es redactar tu respuesta final completa, fundamentada y estructurada en texto natural, basándote en las fuentes oficiales recopiladas. "
                            "Está ESTRICTAMENTE PROHIBIDO emitir etiquetas '<tool_call>', funciones simuladas o postergar la respuesta: redacta tu conclusión definitiva de inmediato."
                        )
                        m["content"] = f"{base_txt}{closure_directive}"
                    elif governor_action in ["max_calls_abstention", "insufficient_data_cut"]:
                        closure_directive = (
                            "\n\n[FASE DE INVESTIGACIÓN CONCLUIDA - INSUFICIENCIA DE FUENTES (MEA)]:\n"
                            f"Se ha alcanzado el límite de {tool_count} rondas de búsqueda con fuentes oficiales insuficientes. "
                            "Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas. "
                            "Conforme al Invariante de Veracidad, redacta tu respuesta declarando formalmente: 'No tengo datos suficientes en las fuentes oficiales de la base documental para responder a esta consulta con certeza.' "
                            "Está terminantemente prohibido inventar datos de memoria paramétrica ni emitir etiquetas '<tool_call>'."
                        )
                        m["content"] = f"{base_txt}{closure_directive}"
                    else:
                        # En zona condicional o zona suficiente, limpiar la orden de forzado de primer token
                        # para que el modelo pueda emitir texto libre (abstención o síntesis) o llamar a otra tool
                        m["content"] = base_txt
                elif isinstance(c, list):
                    for part in c:
                        if isinstance(part, dict) and part.get("type") == "text":
                            ptxt = part.get("text", "")
                            if "[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO" in ptxt:
                                base_txt = re.split(r"\n\n\[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", ptxt)[0].strip()
                                if governor_action in ["hard_cap", "max_calls_synthesis"]:
                                    closure_directive = (
                                        "\n\n[FASE DE INVESTIGACIÓN CONCLUIDA - SÍNTESIS FINAL OBLIGATORIA (MEA)]:\n"
                                        f"La fase de recuperación documental ha concluido (~{tool_tokens:,} tokens en {tool_count} llamada/s). "
                                        "Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas. "
                                        "Redacta de inmediato tu respuesta final en texto estructurado basándote en las fuentes oficiales recopiladas. "
                                        "Está ESTRICTAMENTE PROHIBIDO emitir etiquetas '<tool_call>'."
                                    )
                                    part["text"] = f"{base_txt}{closure_directive}"
                                elif governor_action in ["max_calls_abstention", "insufficient_data_cut"]:
                                    closure_directive = (
                                        "\n\n[FASE DE INVESTIGACIÓN CONCLUIDA - INSUFICIENCIA DE FUENTES (MEA)]:\n"
                                        f"Se ha alcanzado el límite de {tool_count} rondas de búsqueda con fuentes oficiales insuficientes. "
                                        "Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas. "
                                        "Declara formalmente la falta de datos suficientes sin inventar de memoria paramétrica ni emitir etiquetas '<tool_call>'."
                                    )
                                    part["text"] = f"{base_txt}{closure_directive}"
                                else:
                                    part["text"] = base_txt
                break

    # Inyectar el banner en el último mensaje 'tool' si se definió una directiva
    if banner and 0 <= last_tool_idx < len(messages):
        last_m = dict(messages[last_tool_idx])
        curr_content = last_m.get("content", "")
        if isinstance(curr_content, str):
            # Evitar inyecciones duplicadas si el payload pasa varias veces por enriquecimiento
            if "[GOBERNADOR RAG" not in curr_content and "[DICTAMEN RAG" not in curr_content:
                last_m["content"] = curr_content + banner
                messages[last_tool_idx] = last_m

    return data, {
        "status": "applied",
        "action": governor_action,
        "tool_call_count": tool_count,
        "accumulated_tool_tokens": tool_tokens,
        "is_sufficient": is_sufficient,
        "eval_reason": eval_reason,
        "tools_disabled": "tools" not in data
    }


def normalize_tool_call_signature(fn_name: str, arguments: Any) -> Tuple[str, str]:
    """
    Retorna una firma determinista (fn_name, canonical_args_json) para comparar
    llamadas a herramientas en el mismo turno.
    Normaliza strings JSON, orden de claves y mayúsculas/espacios en campos de texto.
    """
    import json

    fn_clean = (fn_name or "").strip()
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except Exception:
            return (fn_clean, arguments.strip().lower())
    elif isinstance(arguments, dict):
        parsed = arguments
    else:
        return (fn_clean, str(arguments or "").strip().lower())

    if isinstance(parsed, dict):
        normalized_dict = {}
        for k, v in parsed.items():
            k_clean = str(k).strip().lower()
            if isinstance(v, str):
                normalized_dict[k_clean] = v.strip().lower()
            elif isinstance(v, list):
                normalized_dict[k_clean] = [x.strip().lower() if isinstance(x, str) else x for x in v]
            elif isinstance(v, dict):
                normalized_dict[k_clean] = {str(dk).strip().lower(): (dv.strip().lower() if isinstance(dv, str) else dv) for dk, dv in v.items()}
            else:
                normalized_dict[k_clean] = v
        canonical_args = json.dumps(normalized_dict, sort_keys=True, ensure_ascii=False)
    else:
        canonical_args = json.dumps(parsed, sort_keys=True, ensure_ascii=False)

    return (fn_clean, canonical_args)


def deduplicate_tool_calls(tool_calls: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Filtra llamadas a herramientas con consultas o argumentos idénticos en una misma ráfaga o turno.
    Preserva el orden original de la primera aparición de cada llamada única y re-indexa.
    Retorna la lista de tool_calls deduplicada y la cantidad de duplicados descartados.
    """
    if not tool_calls or not isinstance(tool_calls, list):
        return tool_calls or [], 0

    seen_signatures = set()
    deduped = []
    duplicates_count = 0

    for tc in tool_calls:
        if not isinstance(tc, dict):
            deduped.append(tc)
            continue

        fn_obj = tc.get("function", {})
        fn_name = fn_obj.get("name") or tc.get("name") or ""
        args = fn_obj.get("arguments") if "function" in tc else tc.get("arguments")

        sig = normalize_tool_call_signature(fn_name, args)
        if sig in seen_signatures:
            duplicates_count += 1
            continue

        seen_signatures.add(sig)
        cloned_tc = dict(tc)
        cloned_tc["index"] = len(deduped)
        deduped.append(cloned_tc)

    return deduped, duplicates_count


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
                    deduped_calls, dups = deduplicate_tool_calls(calls)
                    if dups > 0:
                        print(f"🧹 [Tool Governor] Deduplicadas {dups} llamada/s a herramientas idénticas en array crudo ({len(calls)} ➔ {len(deduped_calls)}).", flush=True)
                    return deduped_calls
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

