import os
import unittest
from gateway.core.context_pruner import (
    prune_chat_history,
    get_max_user_turns,
    get_max_context_tokens,
    get_keep_tool_turns,
    estimate_tokens,
    DEFAULT_MAX_USER_TURNS,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_KEEP_TOOL_TURNS
)


class TestContextPruner(unittest.TestCase):

    def setUp(self):
        # Asegurar estado limpio de variables de entorno
        for env_var in ["GATEWAY_MAX_USER_TURNS", "GATEWAY_MAX_CONTEXT_TOKENS", "GATEWAY_KEEP_TOOL_TURNS"]:
            if env_var in os.environ:
                del os.environ[env_var]

    def test_default_settings(self):
        self.assertEqual(get_max_user_turns(), DEFAULT_MAX_USER_TURNS)
        self.assertEqual(get_max_user_turns(), 6)
        self.assertEqual(get_max_context_tokens(), DEFAULT_MAX_CONTEXT_TOKENS)
        self.assertEqual(get_max_context_tokens(), 32000)
        self.assertEqual(get_keep_tool_turns(), DEFAULT_KEEP_TOOL_TURNS)
        self.assertEqual(get_keep_tool_turns(), 2)

    def test_env_var_overrides(self):
        os.environ["GATEWAY_MAX_USER_TURNS"] = "10"
        os.environ["GATEWAY_MAX_CONTEXT_TOKENS"] = "50000"
        os.environ["GATEWAY_KEEP_TOOL_TURNS"] = "3"

        self.assertEqual(get_max_user_turns(), 10)
        self.assertEqual(get_max_context_tokens(), 50000)
        self.assertEqual(get_keep_tool_turns(), 3)

        del os.environ["GATEWAY_MAX_USER_TURNS"]
        del os.environ["GATEWAY_MAX_CONTEXT_TOKENS"]
        del os.environ["GATEWAY_KEEP_TOOL_TURNS"]

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
                "content": f"Resultado búsqueda corta {i}"
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

        # Verificar que no hay ningún mensaje 'tool' huérfano sin assistant previo
        for idx, m in enumerate(pruned):
            if m.get("role") == "tool":
                prev_m = pruned[idx - 1]
                self.assertEqual(prev_m.get("role"), "assistant")
                self.assertIsNotNone(prev_m.get("tool_calls"))

    def test_tool_output_compaction_for_older_turns(self):
        # 5 turnos de usuario, cada uno con una respuesta de herramienta extensa (> 250 caracteres)
        # Con keep_tool_turns=2, los turnos 1, 2, 3 deben compactar sus tool outputs,
        # mientras que los turnos 4 y 5 deben conservar el texto original completo.
        messages = [{"role": "system", "content": "System prompt"}]
        long_legal_text = "Artículo 1: Toda persona tiene derecho a..." * 20  # ~860 chars

        for i in range(1, 6):
            messages.append({"role": "user", "content": f"Turno {i}"})
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": f"call_{i}", "function": {"name": "leer_documento", "arguments": "{}"}}]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": f"Documento {i}: {long_legal_text}"
            })
            messages.append({"role": "assistant", "content": f"Síntesis del turno {i}"})

        pruned, dropped = prune_chat_history(
            messages,
            max_user_turns=18,
            keep_tool_turns=2
        )
        self.assertEqual(dropped, 0)  # No se descartan turnos porque 5 <= 18

        # Extraer los mensajes tool
        tool_msgs = [m for m in pruned if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 5)

        # Turnos 1, 2 y 3: deben tener contenido archivado
        for idx in [0, 1, 2]:
            self.assertIn("[Contenido de herramienta archivado para optimizar contexto:", tool_msgs[idx]["content"])
            self.assertEqual(tool_msgs[idx]["tool_call_id"], f"call_{idx+1}")

        # Turnos 4 y 5: deben tener el texto legal completo
        for idx in [3, 4]:
            self.assertIn(long_legal_text, tool_msgs[idx]["content"])
            self.assertEqual(tool_msgs[idx]["tool_call_id"], f"call_{idx+1}")

    def test_assistant_output_compaction_for_older_turns(self):
        # 5 turnos de usuario, cada uno con una respuesta de asistente extensa (> 600 caracteres)
        # Con keep_tool_turns=2, los turnos 1, 2, 3 deben compactar sus respuestas de asistente,
        # mientras que los turnos 4 y 5 deben conservar el texto original completo.
        messages = [{"role": "system", "content": "System prompt"}]
        long_assistant_text = "Síntesis inicial del tema.\n\n| Tabla | Detalle |\n|---|---|\n" + ("| Norma | Contenido extenso |\n" * 30)

        for i in range(1, 6):
            messages.append({"role": "user", "content": f"Turno {i}"})
            messages.append({"role": "assistant", "content": f"Turno {i}: {long_assistant_text}"})

        pruned, dropped = prune_chat_history(
            messages,
            max_user_turns=10,
            keep_tool_turns=2
        )
        self.assertEqual(dropped, 0)
        asst_msgs = [m for m in pruned if m.get("role") == "assistant"]
        self.assertEqual(len(asst_msgs), 5)

        # Turnos 1, 2 y 3 (índices 0, 1, 2): compactados
        for idx in [0, 1, 2]:
            self.assertIn("[Detalle normativo extenso y tablas archivadas para optimizar contexto:", asst_msgs[idx]["content"])
            self.assertTrue(asst_msgs[idx]["content"].startswith(f"Turno {idx+1}: Síntesis inicial del tema."))

        # Turnos 4 y 5 (índices 3, 4): intactos
        for idx in [3, 4]:
            self.assertNotIn("[Detalle normativo extenso y tablas archivadas", asst_msgs[idx]["content"])
            self.assertIn(long_assistant_text, asst_msgs[idx]["content"])

    def test_token_budget_cap_enforcement(self):
        # Conversación dentro del límite de 18 turnos (ej. 4 turnos),
        # pero donde cada mensaje contiene un texto tan largo que excede el max_context_tokens
        messages = [{"role": "system", "content": "Sys"}]
        huge_text = "Palabra " * 1000  # ~8000 caracteres (~2285 tokens)
        for i in range(1, 5):
            messages.append({"role": "user", "content": f"Turno {i}: {huge_text}"})
            messages.append({"role": "assistant", "content": f"Respuesta {i}: {huge_text}"})

        # Cap estricto de 3000 tokens: cada turno completo tiene ~4500 tokens.
        # Por ende, solo debe poder conservar 1 turno (el último)
        pruned, dropped = prune_chat_history(
            messages,
            max_user_turns=18,
            max_context_tokens=3000
        )
        # Deben haberse descartado 3 turnos para encajar en el presupuesto
        self.assertEqual(dropped, 3)
        user_msgs = [m for m in pruned if m.get("role") == "user"]
        self.assertEqual(len(user_msgs), 1)
        self.assertTrue(user_msgs[0]["content"].startswith("Turno 4"))

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

    def test_default_6_turns_pruning(self):
        # 15 turnos de usuario -> deben conservarse 6 y descartarse 9 con defaults
        messages = [{"role": "system", "content": "Sys"}]
        for i in range(1, 16):
            messages.append({"role": "user", "content": f"Turno {i}"})
            messages.append({"role": "assistant", "content": f"Resp {i}"})

        pruned, dropped = prune_chat_history(messages)
        self.assertEqual(dropped, 9)
        user_msgs = [m for m in pruned if m.get("role") == "user"]
        self.assertEqual(len(user_msgs), 6)
        self.assertEqual(user_msgs[0]["content"], "Turno 10")
        self.assertEqual(user_msgs[-1]["content"], "Turno 15")

    def test_cache_prompt_injection_on_pruning(self):
        import asyncio
        from gateway.core.alignment_engine import enrich_chat_payload

        # Conversación con 15 turnos (supera el default de 10)
        messages = [{"role": "system", "content": "Sys"}]
        for i in range(1, 16):
            messages.append({"role": "user", "content": f"Turno {i}"})
            messages.append({"role": "assistant", "content": f"Resp {i}"})

        payload = {"messages": messages, "tools": []}
        enriched = asyncio.run(enrich_chat_payload(payload, actual_model="gpt-oss-20b", is_cloud_request=False))
        self.assertFalse(enriched.get("cache_prompt"))

    def test_slot_flusher_mocked(self):
        import asyncio
        from unittest.mock import AsyncMock, patch, MagicMock
        from gateway.core.slot_flusher import flush_llama_slots

        # Simular respuestas HTTP exitosas para /slots y /slots/{id}?action=erase
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = [{"id": 0}, {"id": 1}]

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_get.return_value = mock_get_resp
                mock_post.return_value = mock_post_resp

                success = asyncio.run(flush_llama_slots(target_port=18100))
                self.assertTrue(success)
                self.assertEqual(mock_post.call_count, 2)

    def test_massive_tool_turn_compacts_tools_instead_of_dropping_turn(self):
        # Simula una consulta jurídica previa con 12 tool calls (~50k tokens de evidencia)
        # seguida inmediatamente de una repregunta breve ("Pasamelo en PDF").
        # El podador NO debe descartar el turno 1, sino compactar las tools del turno 1
        # y preservar 100% íntegra la síntesis del asistente.
        messages = [{"role": "system", "content": "System prompt"}]
        messages.append({"role": "user", "content": "Tratados con jerarquía constitucional en la CN"})
        for i in range(12):
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": f"c_{i}", "function": {"name": "leer_documento_completo", "arguments": "{}"}}]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": f"c_{i}",
                "content": "Extracto normativo extenso " * 500  # ~14.000 chars cada uno
            })
        full_assistant_synthesis = (
            "# Tratados Internacionales con Jerarquía Constitucional (Art. 75 inc. 22)\n\n"
            "A continuación se detallan los 14 instrumentos con jerarquía constitucional:\n"
            + ("| Instrumento | Jerarquía | Ámbito |\n|---|---|---|\n" + "| Tratado Internacional | Constitucional | DDHH |\n" * 15)
        )
        messages.append({"role": "assistant", "content": full_assistant_synthesis})
        messages.append({"role": "user", "content": "Pasamelo en PDF"})

        pruned, dropped = prune_chat_history(messages, max_context_tokens=32000)

        # 0 turnos descartados
        self.assertEqual(dropped, 0)

        # Ambos mensajes de usuario deben estar presentes
        user_msgs = [m for m in pruned if m.get("role") == "user"]
        self.assertEqual(len(user_msgs), 2)
        self.assertEqual(user_msgs[0]["content"], "Tratados con jerarquía constitucional en la CN")
        self.assertEqual(user_msgs[1]["content"], "Pasamelo en PDF")

        # La síntesis final del asistente debe conservarse completa sin mutilación
        final_asst = [m for m in pruned if m.get("role") == "assistant" and not m.get("tool_calls")][0]
        self.assertEqual(final_asst["content"], full_assistant_synthesis)

        # Los tool outputs del turno 1 deben haber sido compactados
        tool_msgs = [m for m in pruned if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 12)
        for tm in tool_msgs:
            self.assertIn("[Contenido de herramienta archivado para optimizar contexto:", tm["content"])

        # El conteo total estimado de tokens debe encajar holgadamente en el límite de 32k
        total_tokens = estimate_tokens(pruned, base_overhead=5000)
        self.assertLessEqual(total_tokens, 32000)


if __name__ == "__main__":
    unittest.main()
