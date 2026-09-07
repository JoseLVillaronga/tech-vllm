import os
import unittest
from gateway.core.context_pruner import prune_chat_history, get_max_user_turns


class TestContextPruner(unittest.TestCase):

    def setUp(self):
        # Asegurar estado limpio de variable de entorno
        if "GATEWAY_MAX_USER_TURNS" in os.environ:
            del os.environ["GATEWAY_MAX_USER_TURNS"]

    def test_default_max_user_turns(self):
        self.assertEqual(get_max_user_turns(), 18)

    def test_env_var_override(self):
        os.environ["GATEWAY_MAX_USER_TURNS"] = "10"
        self.assertEqual(get_max_user_turns(), 10)
        del os.environ["GATEWAY_MAX_USER_TURNS"]

    def test_short_conversation_not_pruned(self):
        messages = [
            {"role": "system", "content": "Eres un asistente."},
            {"role": "user", "content": "Hola"},
            {"role": "assistant", "content": "Hola, ¿en qué puedo ayudarte?"},
            {"role": "user", "content": "¿Cómo estás?"},
            {"role": "assistant", "content": "Muy bien, gracias."}
        ]
        pruned, dropped = prune_chat_history(messages, max_user_turns=18)
        self.assertEqual(dropped, 0)
        self.assertEqual(len(pruned), len(messages))
        self.assertEqual(pruned, messages)

    def test_long_conversation_pruned_to_exact_limit(self):
        # Crear conversación con 25 turnos de usuario
        messages = [{"role": "system", "content": "System prompt rector"}]
        for i in range(1, 26):
            messages.append({"role": "user", "content": f"Pregunta {i}"})
            messages.append({"role": "assistant", "content": f"Respuesta {i}"})

        pruned, dropped = prune_chat_history(messages, max_user_turns=18)
        
        # Deben descartarse los primeros 7 turnos (25 - 18 = 7)
        self.assertEqual(dropped, 7)
        
        # El primer mensaje debe ser el system prompt original
        self.assertEqual(pruned[0]["role"], "system")
        self.assertEqual(pruned[0]["content"], "System prompt rector")
        
        # El primer mensaje de usuario debe ser la pregunta 8 (25 - 18 + 1)
        self.assertEqual(pruned[1]["role"], "user")
        self.assertEqual(pruned[1]["content"], "Pregunta 8")
        
        # El último mensaje debe ser la respuesta 25
        self.assertEqual(pruned[-1]["role"], "assistant")
        self.assertEqual(pruned[-1]["content"], "Respuesta 25")
        
        # Total de turnos de usuario conservados = exactamente 18
        user_turns_count = sum(1 for m in pruned if m.get("role") == "user")
        self.assertEqual(user_turns_count, 18)

    def test_atomic_tool_call_sequence_preserved(self):
        # Crear conversación donde cada turno tiene tool calls
        messages = [{"role": "system", "content": "System prompt"}]
        for i in range(1, 22):
            messages.append({"role": "user", "content": f"Consulta jurídica {i}"})
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": f"call_{i}", "function": {"name": "buscar", "arguments": "{}"}}]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": f"Resultado búsqueda {i}"
            })
            messages.append({"role": "assistant", "content": f"Respuesta jurídica final {i}"})

        # 21 turnos de usuario, limitados a 18 -> deben descartarse 3 turnos (1, 2, 3)
        pruned, dropped = prune_chat_history(messages, max_user_turns=18)
        self.assertEqual(dropped, 3)

        # El primer mensaje después del system debe ser el usuario del turno 4
        self.assertEqual(pruned[0]["role"], "system")
        self.assertEqual(pruned[1]["role"], "user")
        self.assertEqual(pruned[1]["content"], "Consulta jurídica 4")

        # Verificar que el bloque del turno 4 contiene el tool call y tool result intactos
        self.assertEqual(pruned[2]["role"], "assistant")
        self.assertIsNotNone(pruned[2].get("tool_calls"))
        self.assertEqual(pruned[3]["role"], "tool")
        self.assertEqual(pruned[3]["tool_call_id"], "call_4")
        self.assertEqual(pruned[4]["role"], "assistant")
        self.assertEqual(pruned[4]["content"], "Respuesta jurídica final 4")

        # Verificar que no hay ningún mensaje 'tool' que no tenga un assistant previo
        for idx, m in enumerate(pruned):
            if m.get("role") == "tool":
                prev_m = pruned[idx - 1]
                self.assertEqual(prev_m.get("role"), "assistant")
                self.assertIsNotNone(prev_m.get("tool_calls"))

    def test_multiple_system_prompts_preserved(self):
        messages = [
            {"role": "system", "content": "Sys 1"},
            {"role": "system", "content": "Sys 2"},
            {"role": "user", "content": "Hola 1"},
            {"role": "assistant", "content": "Resp 1"},
            {"role": "user", "content": "Hola 2"},
            {"role": "assistant", "content": "Resp 2"},
        ]
        pruned, dropped = prune_chat_history(messages, max_user_turns=1)
        self.assertEqual(dropped, 1)
        self.assertEqual(pruned[0]["content"], "Sys 1")
        self.assertEqual(pruned[1]["content"], "Sys 2")
        self.assertEqual(pruned[2]["content"], "Hola 2")
        self.assertEqual(pruned[3]["content"], "Resp 2")

    def test_empty_or_single_message(self):
        self.assertEqual(pruned := prune_chat_history([]), ([], 0))
        single = [{"role": "system", "content": "Hola"}]
        self.assertEqual(prune_chat_history(single), (single, 0))


if __name__ == "__main__":
    unittest.main()
