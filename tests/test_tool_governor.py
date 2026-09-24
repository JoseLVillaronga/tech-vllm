import unittest
from gateway.core.tool_governor import (
    inspect_active_turn_tools,
    apply_tool_budget_governor,
    is_broad_or_deep_query,
    parse_raw_tool_calls,
    deduplicate_tool_calls,
    normalize_tool_call_signature,
    DEFAULT_MAX_TOOL_TOKENS,
    DEFAULT_INSUFFICIENT_TOOL_TOKENS,
    DEFAULT_MIN_TOOL_TOKENS,
    DEFAULT_MAX_EXPLORATION_CALLS
)


import os
from unittest.mock import patch


class TestToolGovernor(unittest.TestCase):

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {
            "GATEWAY_MAX_TOOL_CALLS_PER_TURN": "7",
            "GATEWAY_MAX_TOOL_TOKENS": "50000",
            "GATEWAY_MIN_TOOL_TOKENS": "10000",
            "GATEWAY_INSUFFICIENT_TOOL_TOKENS": "5000",
            "GATEWAY_MAX_EXPLORATION_CALLS": "4",
        })
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

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

    def test_conditional_governance_insufficient_data(self):
        # 2 llamadas con texto insuficiente: las herramientas deben permanecer activas con dictamen condicional
        messages = [
            {"role": "user", "content": "Tratado interplanetario sobre minería lunar"},
            {"role": "assistant", "tool_calls": [{"id": "c_1", "function": {"name": "buscar"}}]},
            {"role": "tool", "tool_call_id": "c_1", "content": "No se encontraron fragmentos relevantes en la base documental."},
        ]

        data = {
            "model": "Qwen3.6-35B-A3B-Q4_K_M",
            "tools": [{"type": "function", "function": {"name": "buscar"}}],
            "messages": messages
        }

        modified_data, report = apply_tool_budget_governor(data)

        self.assertEqual(report["action"], "conditional_insufficient")
        self.assertFalse(report["tools_disabled"])
        self.assertIn("tools", modified_data)

        last_tool = modified_data["messages"][-1]
        self.assertIn("⚠️ [DICTAMEN RAG - CONDICIÓN DE SUFICIENCIA]", last_tool["content"])
        self.assertIn("SI Y SOLO SI vas a contestar definitivamente", last_tool["content"])
        self.assertIn("DEBES ABSTENERTE", last_tool["content"])
        self.assertIn("SI CONSIDERAS NECESARIO PROFUNDIZAR", last_tool["content"])

    def test_max_calls_abstention_after_7_calls(self):
        # 7 llamadas con datos insuficientes: circuit breaker duro por cupo de consultas (abstención)
        messages = [
            {
                "role": "user",
                "content": "Tratado desconocido\n\n[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]:\nTu primer token emitido DEBE ser la llamada a la herramienta formal (<tool_call>)."
            },
        ]
        for i in range(7):
            messages.append({"role": "assistant", "tool_calls": [{"id": f"c_{i}", "function": {"name": "buscar"}}]})
            messages.append({"role": "tool", "tool_call_id": f"c_{i}", "content": "No se encontraron fragmentos relevantes."})

        data = {
            "model": "Qwen3.6-35B-A3B-Q4_K_M",
            "tools": [{"type": "function", "function": {"name": "buscar"}}],
            "messages": messages
        }

        modified_data, report = apply_tool_budget_governor(data)

        self.assertEqual(report["action"], "max_calls_abstention")
        self.assertTrue(report["tools_disabled"])
        self.assertNotIn("tools", modified_data)

        last_tool = modified_data["messages"][-1]
        self.assertIn("⚠️ [GOBERNADOR RAG - LÍMITE DE CONSULTAS ALCANZADO (ABSTENCIÓN MEA)]", last_tool["content"])
        self.assertIn("No tengo datos suficientes en las fuentes oficiales", last_tool["content"])

        user_msg = modified_data["messages"][0]["content"]
        self.assertNotIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", user_msg)
        self.assertIn("[FASE DE INVESTIGACIÓN CONCLUIDA - INSUFICIENCIA DE FUENTES (MEA)]", user_msg)

    def test_max_calls_synthesis_after_7_calls(self):
        # 7 llamadas con datos suficientes (fast pass de alta coincidencia): circuit breaker duro (síntesis)
        chunk = "--- FUENTE [1]: \"Ley Oficial\" (Tema: Derecho | Sección: General | Autor: Congreso | Similitud: 92%) ---\nEl artículo 1 establece claramente la norma aplicable."
        messages = [
            {
                "role": "user",
                "content": "¿Qué dispone el artículo 1 de la norma?\n\n[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]:\nTu primer token emitido DEBE ser la llamada a la herramienta formal (<tool_call>)."
            },
        ]
        for i in range(7):
            messages.append({"role": "assistant", "tool_calls": [{"id": f"c_{i}", "function": {"name": "buscar"}}]})
            messages.append({"role": "tool", "tool_call_id": f"c_{i}", "content": chunk})

        data = {
            "model": "Qwen3.6-35B-A3B-Q4_K_M",
            "tools": [{"type": "function", "function": {"name": "buscar"}}],
            "messages": messages
        }

        modified_data, report = apply_tool_budget_governor(data)

        self.assertEqual(report["action"], "max_calls_synthesis")
        self.assertTrue(report["tools_disabled"])
        self.assertNotIn("tools", modified_data)

        last_tool = modified_data["messages"][-1]
        self.assertIn("🛑 [GOBERNADOR RAG - LÍMITE DE CONSULTAS ALCANZADO]", last_tool["content"])
        self.assertIn("Proceda de inmediato a redactar su respuesta final", last_tool["content"])

        user_msg = modified_data["messages"][0]["content"]
        self.assertNotIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", user_msg)
        self.assertIn("[FASE DE INVESTIGACIÓN CONCLUIDA - SÍNTESIS FINAL OBLIGATORIA (MEA)]", user_msg)

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

    def test_parse_raw_tool_calls_json_array(self):
        valid_tools = {"buscar_en_base_de_conocimiento", "leer_documento_completo"}
        raw_json = '[{"name": "buscar_en_base_de_conocimiento", "arguments": {"consulta": "Tratados internacionales"}}]'
        res = parse_raw_tool_calls(raw_json, valid_tools)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["function"]["name"], "buscar_en_base_de_conocimiento")
        self.assertIn("Tratados internacionales", res[0]["function"]["arguments"])

    def test_parse_raw_tool_calls_bracketed_format(self):
        valid_tools = {"buscar_en_base_de_conocimiento"}
        raw_bracketed = '[buscar_en_base_de_conocimiento[CALL_ID]call_999[ARGS]{"consulta": "Constitución", "dominios": "Derecho"}]'
        res = parse_raw_tool_calls(raw_bracketed, valid_tools)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "call_999")
        self.assertEqual(res[0]["function"]["name"], "buscar_en_base_de_conocimiento")

    def test_parse_raw_tool_calls_negative_cases(self):
        valid_tools = {"buscar_en_base_de_conocimiento"}
        # Texto plano que empieza con corchete pero no es tool call
        self.assertIsNone(parse_raw_tool_calls("[1] Tratados internacionales de la República Argentina.", valid_tools))
        # Herramienta inexistente o no autorizada
        self.assertIsNone(parse_raw_tool_calls('[{"name": "herramienta_prohibida", "arguments": {}}]', valid_tools))
        # Texto vacío
        self.assertIsNone(parse_raw_tool_calls("", valid_tools))

    def test_deduplicate_tool_calls_identical_queries(self):
        calls = [
            {"id": "c1", "type": "function", "function": {"name": "buscar_en_base_de_conocimiento", "arguments": '{"consulta": "tratado antartico ley de glaciares"}'}},
            {"id": "c2", "type": "function", "function": {"name": "buscar_en_base_de_conocimiento", "arguments": '{"consulta": "ley 26639"}'}},
            {"id": "c3", "type": "function", "function": {"name": "buscar_en_base_de_conocimiento", "arguments": '{"consulta": "tratado antartico ley de glaciares"}'}},
            {"id": "c4", "type": "function", "function": {"name": "buscar_en_base_de_conocimiento", "arguments": '{"consulta": "tratado antartico ley de glaciares"}'}},
            {"id": "c5", "type": "function", "function": {"name": "buscar_en_base_de_conocimiento", "arguments": '{"consulta": "ley 26639"}'}},
        ]
        deduped, dups = deduplicate_tool_calls(calls)
        self.assertEqual(dups, 3)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["id"], "c1")
        self.assertEqual(deduped[0]["index"], 0)
        self.assertEqual(deduped[1]["id"], "c2")
        self.assertEqual(deduped[1]["index"], 1)

    def test_deduplicate_tool_calls_case_and_key_order(self):
        calls = [
            {"id": "c1", "type": "function", "function": {"name": "buscar", "arguments": '{"consulta": "Tratado Antartico", "dominios": "Derecho"}'}},
            {"id": "c2", "type": "function", "function": {"name": "buscar", "arguments": '{"dominios": "derecho", "consulta": "  tratado antartico  "}'}},
        ]
        deduped, dups = deduplicate_tool_calls(calls)
        self.assertEqual(dups, 1)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["id"], "c1")

    def test_deduplicate_tool_calls_different_queries_preserved(self):
        # Asegura que si el modelo hace 5 búsquedas semánticas diferentes, NINGUNA se limite
        calls = [
            {"id": f"c{i}", "type": "function", "function": {"name": "buscar", "arguments": f'{{"consulta": "tema {i}"}}'}}
            for i in range(5)
        ]
        deduped, dups = deduplicate_tool_calls(calls)
        self.assertEqual(dups, 0)
        self.assertEqual(len(deduped), 5)

    def test_apply_tool_budget_governor_active_turn_deduplication(self):
        data = {
            "messages": [
                {"role": "user", "content": "Analiza la relación entre tratados y glaciares"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {"id": "call_1", "type": "function", "function": {"name": "buscar", "arguments": '{"consulta": "glaciares"}'}},
                        {"id": "call_2", "type": "function", "function": {"name": "buscar", "arguments": '{"consulta": "glaciares"}'}},
                    ]
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "Resultado 1"},
                {"role": "tool", "tool_call_id": "call_2", "content": "Resultado 2 idéntico"}
            ],
            "tools": [{"type": "function", "function": {"name": "buscar"}}]
        }
        modified_data, report = apply_tool_budget_governor(data)
        ast_msg = modified_data["messages"][1]
        self.assertEqual(len(ast_msg["tool_calls"]), 1)
        self.assertEqual(ast_msg["tool_calls"][0]["id"], "call_1")
        # El mensaje tool duplicado call_2 debe haber sido podado
        tool_msgs = [m for m in modified_data["messages"] if m.get("role") == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertEqual(tool_msgs[0]["tool_call_id"], "call_1")


if __name__ == "__main__":
    unittest.main()

