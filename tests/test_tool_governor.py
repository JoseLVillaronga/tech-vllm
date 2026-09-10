import unittest
from gateway.core.tool_governor import (
    inspect_active_turn_tools,
    apply_tool_budget_governor,
    is_broad_or_deep_query,
    DEFAULT_MAX_TOOL_TOKENS,
    DEFAULT_INSUFFICIENT_TOOL_TOKENS,
    DEFAULT_MIN_TOOL_TOKENS,
    DEFAULT_MAX_EXPLORATION_CALLS
)


class TestToolGovernor(unittest.TestCase):

    def test_broad_or_deep_query_detection(self):
        self.assertTrue(is_broad_or_deep_query("Pasame una lista de tratados internacionales vigentes, fundamenta en profundidad"))
        self.assertTrue(is_broad_or_deep_query("Hacer un análisis comparativo y exhaustivo de todos los contratos"))
        self.assertTrue(is_broad_or_deep_query("Mostrame las obras disponibles en la biblioteca"))
        self.assertTrue(is_broad_or_deep_query("¿Cuáles son los convenios de la OIT ratificados?"))
        self.assertFalse(is_broad_or_deep_query("¿Cuál es la pena para el homicidio simple?"))
        self.assertFalse(is_broad_or_deep_query("Hola, cómo estás?"))

    def test_inspect_active_turn_tools_empty(self):
        stats = inspect_active_turn_tools([])
        self.assertEqual(stats["tool_call_count"], 0)
        self.assertEqual(stats["accumulated_tool_tokens"], 0)
        self.assertEqual(stats["last_tool_idx"], -1)

    def test_inspect_active_turn_tools_multi_turn_isolation(self):
        # Turno 1 (antiguo): Usuario pregunta y modelo usó herramientas
        # Turno 2 (activo): Usuario hace nueva pregunta y modelo usó 2 herramientas
        messages = [
            {"role": "system", "content": "Eres un asistente legal."},
            {"role": "user", "content": "¿Qué es la hipoteca?"},
            {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "buscar"}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "Resultado antiguo" * 50},
            {"role": "assistant", "content": "La hipoteca es un derecho real..."},
            # Turno activo:
            {"role": "user", "content": "Ahora pasame una lista completa de tratados internacionales"},
            {"role": "assistant", "tool_calls": [{"id": "call_2", "function": {"name": "buscar"}}]},
            {"role": "tool", "tool_call_id": "call_2", "content": "Tratado A" * 100},
            {"role": "assistant", "tool_calls": [{"id": "call_3", "function": {"name": "leer"}}]},
            {"role": "tool", "tool_call_id": "call_3", "content": "Tratado B" * 150},
        ]

        stats = inspect_active_turn_tools(messages)
        # Solo debe contar las 2 llamadas del turno activo (call_2 y call_3)
        self.assertEqual(stats["tool_call_count"], 2)
        self.assertEqual(stats["last_tool_idx"], 9)
        self.assertTrue(stats["is_deep_query"])
        self.assertGreater(stats["accumulated_tool_tokens"], 0)

    def test_hard_cap_circuit_breaker(self):
        # Generar contenido que supere los 50.000 tokens (~140.000 caracteres a 2.8 chars/token)
        massive_tool_content = "X" * 150000

        data = {
            "model": "Qwen3.6-35B-A3B-Q4_K_M",
            "tools": [{"type": "function", "function": {"name": "leer_documento_completo"}}],
            "tool_choice": "auto",
            "messages": [
                {
                    "role": "user",
                    "content": "Lista exhaustiva de tratados\n\n[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]:\nTu primer token emitido DEBE ser la llamada a la herramienta formal (<tool_call>)."
                },
                {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "leer_documento_completo"}}]},
                {"role": "tool", "tool_call_id": "call_1", "content": massive_tool_content}
            ]
        }

        modified_data, report = apply_tool_budget_governor(data)

        self.assertEqual(report["action"], "hard_cap")
        self.assertTrue(report["tools_disabled"])
        self.assertNotIn("tools", modified_data)
        self.assertNotIn("tool_choice", modified_data)

        last_tool_msg = modified_data["messages"][2]
        self.assertIn("🛑 [GOBERNADOR RAG - TECHO DE CONTEXTO ALCANZADO]", last_tool_msg["content"])

        # Verificar que la directiva de grounding fue levantada del mensaje del usuario
        user_msg = modified_data["messages"][0]["content"]
        self.assertNotIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", user_msg)
        self.assertIn("[FASE DE INVESTIGACIÓN CONCLUIDA - SÍNTESIS FINAL OBLIGATORIA (MEA)]", user_msg)
        self.assertIn("Queda TERMINANTEMENTE LEVANTADA la obligación de invocar herramientas", user_msg)

    def test_insufficient_data_cut_after_4_calls(self):
        # 4 llamadas con muy poco texto (< 5000 tokens, por ej: ~500 caracteres totales = ~180 tokens)
        messages = [
            {"role": "user", "content": "Tratado extraterrestre intergaláctico"},
        ]
        for i in range(4):
            messages.append({"role": "assistant", "tool_calls": [{"id": f"c_{i}", "function": {"name": "buscar"}}]})
            messages.append({"role": "tool", "tool_call_id": f"c_{i}", "content": "Sin resultados en base de datos."})

        data = {
            "model": "Qwen3.6-35B-A3B-Q4_K_M",
            "tools": [{"type": "function", "function": {"name": "buscar"}}],
            "messages": messages
        }

        modified_data, report = apply_tool_budget_governor(data)

        self.assertEqual(report["action"], "insufficient_data_cut")
        self.assertTrue(report["tools_disabled"])
        self.assertNotIn("tools", modified_data)

        last_tool = modified_data["messages"][-1]
        self.assertIn("⚠️ [GOBERNADOR RAG - FUENTES DOCUMENTALES INSUFICIENTES]", last_tool["content"])
        self.assertIn("No tengo datos suficientes en las fuentes oficiales", last_tool["content"])

    def test_discretionary_zone_after_4_calls(self):
        # 4 llamadas con texto moderado (entre 5.000 y 10.000 tokens: ~20.000 caracteres = ~7.100 tokens)
        chunk = "Contenido normativo oficial del tratado " * 125  # ~5.000 caracteres cada uno
        messages = [
            {"role": "user", "content": "Lista de acuerdos comerciales"},
        ]
        for i in range(4):
            messages.append({"role": "assistant", "tool_calls": [{"id": f"c_{i}", "function": {"name": "leer"}}]})
            messages.append({"role": "tool", "tool_call_id": f"c_{i}", "content": chunk})

        data = {
            "model": "Qwen3.6-35B-A3B-Q4_K_M",
            "tools": [{"type": "function", "function": {"name": "leer"}}],
            "messages": messages
        }

        modified_data, report = apply_tool_budget_governor(data)

        self.assertEqual(report["action"], "discretionary_zone")
        # Herramientas NO deben estar deshabilitadas (el modelo puede continuar a su criterio)
        self.assertFalse(report["tools_disabled"])
        self.assertIn("tools", modified_data)

        last_tool = modified_data["messages"][-1]
        self.assertIn("ℹ️ [GOBERNADOR RAG - ZONA DISCRECIONAL]", last_tool["content"])
        self.assertIn("puede continuar haciendo llamadas a herramientas a su propio criterio", last_tool["content"])

    def test_healthy_zone_above_10k_tokens(self):
        # Acumulando > 10.000 tokens (ej: 29 chars * 1100 = 31.900 caracteres / 2.8 = ~11.392 tokens)
        big_chunk = "Texto de ley oficial extenso " * 1100
        data = {
            "model": "Qwen3.6-35B-A3B-Q4_K_M",
            "tools": [{"type": "function", "function": {"name": "leer"}}],
            "messages": [
                {"role": "user", "content": "Análisis de convenios"},
                {"role": "assistant", "tool_calls": [{"id": "c_1", "function": {"name": "leer"}}]},
                {"role": "tool", "tool_call_id": "c_1", "content": big_chunk}
            ]
        }

        modified_data, report = apply_tool_budget_governor(data)

        self.assertEqual(report["action"], "healthy_zone")
        self.assertFalse(report["tools_disabled"])
        self.assertIn("tools", modified_data)

        last_tool = modified_data["messages"][-1]
        self.assertIn("✅ [GOBERNADOR RAG - EVIDENCIA ROBUSTA]", last_tool["content"])


if __name__ == "__main__":
    unittest.main()

