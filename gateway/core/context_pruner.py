import os
from typing import List, Dict, Any, Tuple


DEFAULT_MAX_USER_TURNS = 6
DEFAULT_MAX_CONTEXT_TOKENS = 32000
DEFAULT_KEEP_TOOL_TURNS = 2
CHARS_PER_TOKEN_ESTIMATE = 2.8
BASE_PROMPT_OVERHEAD_TOKENS = 5000


def get_max_user_turns() -> int:
    """Obtiene el número máximo de turnos de usuario a retener desde el entorno o usa el valor por defecto (6)."""
    try:
        val = int(os.getenv("GATEWAY_MAX_USER_TURNS", str(DEFAULT_MAX_USER_TURNS)))
        return max(1, val)
    except (ValueError, TypeError):
        return DEFAULT_MAX_USER_TURNS


def get_max_context_tokens() -> int:
    """Obtiene el techo máximo seguro de tokens de contexto desde el entorno o usa el valor por defecto (32000)."""
    try:
        val = int(os.getenv("GATEWAY_MAX_CONTEXT_TOKENS", str(DEFAULT_MAX_CONTEXT_TOKENS)))
        return max(1000, val)
    except (ValueError, TypeError):
        return DEFAULT_MAX_CONTEXT_TOKENS


def get_keep_tool_turns() -> int:
    """Obtiene la cantidad de turnos recientes cuyos tool outputs se mantienen íntegros (por defecto 2)."""
    try:
        val = int(os.getenv("GATEWAY_KEEP_TOOL_TURNS", str(DEFAULT_KEEP_TOOL_TURNS)))
        return max(0, val)
    except (ValueError, TypeError):
        return DEFAULT_KEEP_TOOL_TURNS


def estimate_tokens(messages: List[Dict[str, Any]], base_overhead: int = 0) -> int:
    """
    Estima de forma precisa el conteo de tokens del payload en base al conteo de caracteres.
    Para español técnico/jurídico con formateo markdown y JSON, ~2.8 caracteres equivalen a 1 token.
    Permite incorporar el sobrecosto base (ej: ~5000 tokens de herramientas e invariantes).
    """
    total_chars = 0
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            total_chars += len(c)
        elif isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and "text" in part:
                    total_chars += len(str(part.get("text", "")))
        tc = m.get("tool_calls")
        if tc:
            total_chars += len(str(tc))
    tokens = int(total_chars / CHARS_PER_TOKEN_ESTIMATE)
    if messages and base_overhead > 0:
        tokens += base_overhead
    return tokens


def prune_chat_history(
    messages: List[Dict[str, Any]],
    max_user_turns: int = None,
    max_context_tokens: int = None,
    keep_tool_turns: int = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Poda el historial de conversación aplicando una ventana deslizante inteligente (Olvido Selectivo):
    1. Preserva intactos los mensajes iniciales con role == 'system'.
    2. Agrupa el diálogo en 'bloques atómicos de turno' delimitados por cada mensaje con role == 'user'.
    3. Si la cantidad de turnos de usuario excede 'max_user_turns' (10), descarta los bloques más antiguos.
    4. Compacta los outputs de herramientas (role == 'tool') de turnos antiguos (> keep_tool_turns),
       preservando intactos únicamente los turnos recientes donde el usuario aún puede repreguntar sobre el documento.
    5. Verifica el techo de seguridad de tokens ('max_context_tokens', por defecto 32.000). Si tras compactar
       herramientas se supera el umbral, descarta turnos antiguos adicionales hasta encajar en el presupuesto.
    6. Garantiza la atomicidad estricta de las herramientas: jamás separa un assistant con tool_calls de sus tools.

    Retorna:
        Tuple[List[Dict[str, Any]], int]: (mensajes_podados, cantidad_de_turnos_descartados)
    """
    if not messages or not isinstance(messages, list) or len(messages) <= 1:
        return messages, 0

    if max_user_turns is None:
        max_user_turns = get_max_user_turns()
    if max_context_tokens is None:
        max_context_tokens = get_max_context_tokens()
    if keep_tool_turns is None:
        keep_tool_turns = get_keep_tool_turns()

    # 1. Separar mensajes de cabecera del sistema (System Prompts iniciales)
    system_msgs: List[Dict[str, Any]] = []
    idx = 0
    while idx < len(messages) and messages[idx].get("role") == "system":
        system_msgs.append(messages[idx])
        idx += 1

    dialog_msgs = messages[idx:]
    if not dialog_msgs:
        return messages, 0

    # 2. Agrupar el diálogo en bloques atómicos por turno de usuario
    turn_blocks: List[List[Dict[str, Any]]] = []
    current_block: List[Dict[str, Any]] = []

    for msg in dialog_msgs:
        role = msg.get("role")
        if role == "user":
            if current_block:
                turn_blocks.append(current_block)
            current_block = [msg]
        else:
            if current_block:
                current_block.append(msg)
            else:
                current_block = [msg]

    if current_block:
        turn_blocks.append(current_block)

    user_blocks_count = sum(1 for b in turn_blocks if b and b[0].get("role") == "user")

    # 3. Conservar únicamente los últimos max_user_turns bloques que comienzan con 'user'
    kept_blocks: List[List[Dict[str, Any]]] = []
    user_turns_counted = 0

    for block in reversed(turn_blocks):
        is_user_block = bool(block and block[0].get("role") == "user")
        if is_user_block:
            if user_turns_counted < max_user_turns:
                kept_blocks.append(block)
                user_turns_counted += 1
            else:
                break
        else:
            if user_turns_counted < max_user_turns:
                kept_blocks.append(block)

    kept_blocks.reverse()
    dropped_turns = user_blocks_count - user_turns_counted

    # 4. Compactación de tool outputs de turnos antiguos (> keep_tool_turns)
    # Los últimos 'keep_tool_turns' bloques con user retienen herramientas intactas.
    # Los bloques anteriores compactan el texto crudo de 'role: tool' para ahorrar decenas de miles de tokens.
    user_indices = [i for i, b in enumerate(kept_blocks) if b and b[0].get("role") == "user"]
    threshold_idx = user_indices[-keep_tool_turns] if len(user_indices) >= keep_tool_turns else 0

    compacted_blocks: List[List[Dict[str, Any]]] = []
    for block_idx, block in enumerate(kept_blocks):
        is_old_block = (block_idx < threshold_idx)
        processed_block: List[Dict[str, Any]] = []

        for m in block:
            if is_old_block and m.get("role") == "tool":
                content = m.get("content")
                if isinstance(content, str) and len(content) > 250:
                    tool_call_id = m.get("tool_call_id", "")
                    archived_msg = dict(m)
                    archived_msg["content"] = (
                        f"[Contenido de herramienta archivado para optimizar contexto: "
                        f"{len(content)} caracteres previamente sintetizados por el asistente]"
                    )
                    processed_block.append(archived_msg)
                    continue
            elif is_old_block and m.get("role") == "assistant" and not m.get("tool_calls"):
                content = m.get("content")
                if isinstance(content, str) and len(content) > 600:
                    archived_asst = dict(m)
                    cut_idx = content.find("\n|", 100)
                    if cut_idx == -1 or cut_idx > 350:
                        cut_idx = content.find("\n\n", 100)
                    if cut_idx == -1 or cut_idx > 350:
                        cut_idx = 300
                    summary_prefix = content[:cut_idx].strip()
                    archived_asst["content"] = (
                        f"{summary_prefix}\n\n"
                        f"[Detalle normativo extenso y tablas archivadas para optimizar contexto: "
                        f"{len(content) - len(summary_prefix)} caracteres previos]"
                    )
                    processed_block.append(archived_asst)
                    continue
            processed_block.append(m)

        compacted_blocks.append(processed_block)

    kept_blocks = compacted_blocks

    # 5. Aplicar Techo de Seguridad de Tokens (32.000 tokens)
    # Si aun con herramientas compactadas se supera el presupuesto:
    # 5.1 Primero: compactar outputs de herramientas en CUALQUIER turno previo completado
    #     (evita perder la síntesis del asistente y el hilo de la conversación por mero bloat de tools).
    # 5.2 Segundo: si aún supera el techo, compactar respuestas extensas de asistente en turnos viejos.
    # 5.3 Tercero: si aun así supera el techo, descartar los turnos más viejos hasta encajar.
    def flatten(blocks: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        flat: List[Dict[str, Any]] = []
        for b in blocks:
            flat.extend(b)
        return flat

    overhead = BASE_PROMPT_OVERHEAD_TOKENS if max_context_tokens > (BASE_PROMPT_OVERHEAD_TOKENS * 1.5) else 0
    current_total_tokens = estimate_tokens(system_msgs + flatten(kept_blocks), base_overhead=overhead)

    # 5.1 Compactar tools en turnos completados previos si se supera el techo
    if current_total_tokens > max_context_tokens and len(kept_blocks) > 1:
        # Los bloques 0 a len(kept_blocks)-2 son turnos previos ya finalizados
        for b_idx in range(len(kept_blocks) - 1):
            block = kept_blocks[b_idx]
            for m_idx, m in enumerate(block):
                if m.get("role") == "tool":
                    content = m.get("content")
                    if isinstance(content, str) and len(content) > 250 and not content.startswith("[Contenido de herramienta archivado"):
                        archived_msg = dict(m)
                        archived_msg["content"] = (
                            f"[Contenido de herramienta archivado para optimizar contexto: "
                            f"{len(content)} caracteres previamente sintetizados por el asistente]"
                        )
                        block[m_idx] = archived_msg
        current_total_tokens = estimate_tokens(system_msgs + flatten(kept_blocks), base_overhead=overhead)

    # 5.2 Si aún supera el techo, compactar respuestas extensas de asistente en turnos viejos
    if current_total_tokens > max_context_tokens and len(kept_blocks) > 1:
        for b_idx in range(len(kept_blocks) - 1):
            block = kept_blocks[b_idx]
            for m_idx, m in enumerate(block):
                if m.get("role") == "assistant" and not m.get("tool_calls"):
                    content = m.get("content")
                    if isinstance(content, str) and len(content) > 600 and "[Detalle normativo extenso" not in content:
                        archived_asst = dict(m)
                        cut_idx = content.find("\n|", 100)
                        if cut_idx == -1 or cut_idx > 350:
                            cut_idx = content.find("\n\n", 100)
                        if cut_idx == -1 or cut_idx > 350:
                            cut_idx = 300
                        summary_prefix = content[:cut_idx].strip()
                        archived_asst["content"] = (
                            f"{summary_prefix}\n\n"
                            f"[Detalle normativo extenso y tablas archivadas para optimizar contexto: "
                            f"{len(content) - len(summary_prefix)} caracteres previos]"
                        )
                        block[m_idx] = archived_asst
            current_total_tokens = estimate_tokens(system_msgs + flatten(kept_blocks), base_overhead=overhead)
            if current_total_tokens <= max_context_tokens:
                break

    # 5.3 Si aun así supera el techo, descartar los turnos más viejos
    while current_total_tokens > max_context_tokens and len(kept_blocks) > 1:
        discarded = kept_blocks.pop(0)
        if discarded and discarded[0].get("role") == "user":
            dropped_turns += 1
        current_total_tokens = estimate_tokens(system_msgs + flatten(kept_blocks), base_overhead=overhead)

    # 6. Aplanar y validar atomicidad final
    flattened_dialog = flatten(kept_blocks)
    valid_dialog: List[Dict[str, Any]] = []
    skip_orphaned = True
    for m in flattened_dialog:
        if skip_orphaned and m.get("role") == "tool":
            continue  # Descarta tool huérfano si quedó en el límite de corte
        skip_orphaned = False
        valid_dialog.append(m)

    pruned_messages = system_msgs + valid_dialog
    return pruned_messages, dropped_turns
