import os
from typing import List, Dict, Any, Tuple


DEFAULT_MAX_USER_TURNS = 18


def get_max_user_turns() -> int:
    """Obtiene el número máximo de turnos de usuario a retener desde el entorno o usa el valor por defecto (18)."""
    try:
        val = int(os.getenv("GATEWAY_MAX_USER_TURNS", str(DEFAULT_MAX_USER_TURNS)))
        return max(1, val)
    except (ValueError, TypeError):
        return DEFAULT_MAX_USER_TURNS


def prune_chat_history(
    messages: List[Dict[str, Any]],
    max_user_turns: int = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Poda el historial de conversación aplicando una ventana deslizante de turnos de usuario (Olvido Selectivo).
    - Preserva intactos los mensajes iniciales con role == 'system'.
    - Agrupa los mensajes de diálogo en 'bloques atómicos de turno' delimitados por cada mensaje con role == 'user'.
    - Si la cantidad de turnos de usuario excede 'max_user_turns' (por defecto 18), descarta los bloques más antiguos.
    - Garantiza la atomicidad de las herramientas: nunca corta la relación entre un mensaje 'assistant'
      con 'tool_calls' y sus correspondientes mensajes con role == 'tool'.

    Retorna:
        Tuple[List[Dict[str, Any]], int]: (mensajes_podados, cantidad_de_turnos_descartados)
    """
    if not messages or not isinstance(messages, list) or len(messages) <= 1:
        return messages, 0

    if max_user_turns is None:
        max_user_turns = get_max_user_turns()

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
    # Cada bloque comienza con role == 'user' y contiene todos los mensajes subsiguientes
    # (assistant, tool, assistant...) hasta el siguiente mensaje con role == 'user'.
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
                # Caso atípico: mensajes de assistant o tool antes del primer user
                # Los tratamos como un bloque preliminar
                current_block = [msg]

    if current_block:
        turn_blocks.append(current_block)

    # Contar cuántos bloques tienen al usuario como disparador
    user_blocks_count = sum(1 for b in turn_blocks if b and b[0].get("role") == "user")

    # 3. Evaluar si se supera el umbral de turnos
    if user_blocks_count <= max_user_turns:
        return messages, 0

    # 4. Conservar únicamente los últimos max_user_turns bloques que comienzan con 'user'
    # Recorremos desde el final hacia el inicio acumulando bloques
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
            # Mensaje no-user suelto al final o en medio
            if user_turns_counted < max_user_turns:
                kept_blocks.append(block)

    kept_blocks.reverse()
    dropped_turns = user_blocks_count - user_turns_counted

    # 5. Aplanar los bloques seleccionados
    flattened_dialog: List[Dict[str, Any]] = []
    for b in kept_blocks:
        flattened_dialog.extend(b)

    # 6. Verificación estricta de atomicidad para tool calls
    # Asegurar que el primer mensaje no sea un 'tool' huérfano
    valid_dialog: List[Dict[str, Any]] = []
    skip_orphaned = True
    for m in flattened_dialog:
        if skip_orphaned and m.get("role") == "tool":
            continue  # Descarta tool huérfano si quedó al corte
        skip_orphaned = False
        valid_dialog.append(m)

    pruned_messages = system_msgs + valid_dialog
    return pruned_messages, dropped_turns
