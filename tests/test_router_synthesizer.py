import unittest
import asyncio
import json
from unittest.mock import patch, MagicMock
from gateway2.core.router_synthesizer import (
    process_router_synthesizer,
    _execute_local_tool,
    _format_tool_catalog,
    _call_router_slm
)


class TestRouterSynthesizer(unittest.TestCase):

    def test_router_synthesizer_no_tools(self):
        data = {
            "messages": [{"role": "user", "content": "Hola mundo"}]
        }
        res = asyncio.run(process_router_synthesizer(data))
        self.assertEqual(res, data)
        self.assertNotIn("tools", res)

    def test_router_synthesizer_non_rag_query(self):
        data = {
            "messages": [{"role": "user", "content": "Hola, ¿cómo estás?"}],
            "tools": [{"type": "function", "function": {"name": "buscar_en_base_de_conocimiento"}}]
        }
        with patch("gateway2.core.router_synthesizer._call_router_slm") as mock_slm:
            mock_slm.return_value = {"requiere_herramientas": False, "plan": "Saludo", "acciones": []}
            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        self.assertEqual(res["messages"][0]["content"], "Hola, ¿cómo estás?")

    def test_router_synthesizer_rag_query(self):
        data = {
            "messages": [{"role": "user", "content": "¿Cuál es el bien jurídico protegido con más fuerza?"}],
            "tools": [{"type": "function", "function": {"name": "buscar_en_base_de_conocimiento"}}]
        }

        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Buscar en base de conocimiento",
            "acciones": [{"herramienta": "buscar_en_base_de_conocimiento", "parametros": {"consulta": "bien juridico"}}]
        }

        eval_resp = {
            "suficiente": True,
            "motivo": "La evidencia provista define el bien juridico con precision",
            "siguiente_accion": None
        }

        with patch("gateway2.core.router_synthesizer._call_router_slm", side_effect=[plan_resp, eval_resp]), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", return_value=("Busqueda: bien juridico", "Texto normativo sobre la vida humana")):

            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        last_content = res["messages"][0]["content"]
        self.assertIn("<contexto_verificado>", last_content)
        self.assertIn("</contexto_verificado>", last_content)
        self.assertIn("Texto normativo sobre la vida humana", last_content)
        self.assertIn("[INSTRUCCIÓN AL ASISTENTE]", last_content)

    def test_router_synthesizer_insufficient_evidence_abstention(self):
        data = {
            "messages": [{"role": "user", "content": "¿Qué pena tiene la clonación de dinosaurios en el Código Penal?"}],
            "tools": [{"type": "function", "function": {"name": "buscar_en_base_de_conocimiento"}}]
        }

        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Buscar delito en código penal",
            "acciones": [{"herramienta": "buscar_en_base_de_conocimiento", "parametros": {"consulta": "clonacion dinosaurios"}}]
        }

        eval_resp = {
            "suficiente": False,
            "motivo": "No existe tipificación para clonación de dinosaurios en el Código Penal",
            "siguiente_accion": None
        }

        with patch("gateway2.core.router_synthesizer._call_router_slm", side_effect=[plan_resp, eval_resp]), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", return_value=("Búsqueda: clonacion dinosaurios", "Normas sobre animales domésticos")):

            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        last_content = res["messages"][0]["content"]
        self.assertIn("ABSTENCIÓN POR INSUFICIENCIA PROBATORIA - MEA", last_content)
        self.assertIn("Queda TERMINANTEMENTE PROHIBIDO inventar leyes", last_content)

    def test_router_synthesizer_web_search_weather(self):
        data = {
            "messages": [{"role": "user", "content": "Mostrame el pronostico detallado de hoy"}],
            "tools": [
                {"type": "function", "function": {"name": "buscar_en_internet", "description": "Búsqueda web"}},
                {"type": "function", "function": {"name": "get_current_weather", "description": "Clima actual"}}
            ]
        }

        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Consultar clima en vivo",
            "acciones": [{"herramienta": "get_current_weather", "parametros": {"city": "Buenos Aires"}}]
        }
        eval_resp = {
            "suficiente": True,
            "motivo": "Reporte meteorológico completo",
            "siguiente_accion": None
        }

        with patch("gateway2.core.router_synthesizer._call_router_slm", side_effect=[plan_resp, eval_resp]), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", return_value=("Clima: Buenos Aires", "Temperatura: 22°C, Soleado")):

            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        last_content = res["messages"][0]["content"]
        self.assertIn("<contexto_verificado>", last_content)
        self.assertIn("Temperatura: 22°C, Soleado", last_content)

    def test_router_synthesizer_pdf_generation(self):
        data = {
            "messages": [
                {"role": "user", "content": "Mostrame el pronostico"},
                {"role": "assistant", "content": "En Buenos Aires hoy hace 22 grados con cielo despejado."},
                {"role": "user", "content": "Pasamelo en PDF"}
            ],
            "tools": [
                {"type": "function", "function": {"name": "generate_pdf_document", "description": "Genera PDF"}}
            ]
        }

        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Generar documento PDF",
            "acciones": [{"herramienta": "generate_pdf_document", "parametros": {"title": "Pronóstico"}}],
        }

        mock_card = "✅ Archivo PDF compilado exitosamente.\n[📥 Descargar reporte.pdf](http://127.0.0.1:8000/api/tools/pdf/download/123/reporte.pdf)"

        with patch("gateway2.core.router_synthesizer._call_router_slm", return_value=plan_resp), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", return_value=("Generación PDF: reporte.pdf", mock_card)):

            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        last_content = res["messages"][-1]["content"]
        self.assertIn("<contexto_verificado>", last_content)
        self.assertIn("📥 Descargar reporte.pdf", last_content)

    def test_format_tool_catalog(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "buscar_en_internet",
                    "description": "Busca en la web en tiempo real.\nParámetros adicionales...",
                    "parameters": {
                        "properties": {
                            "consulta": {"type": "string"},
                            "max_resultados": {"type": "integer"}
                        }
                    }
                }
            }
        ]
        catalog = _format_tool_catalog(tools)
        self.assertIn("- buscar_en_internet(consulta: string, max_resultados: integer): Busca en la web en tiempo real.", catalog)

    def test_execute_local_tool_mock(self):
        with patch("rag_engine.search_knowledge_base", return_value=[]), \
             patch("rag_engine.format_rag_context_for_llm", return_value="Contexto vacio"):
            lbl, content = _execute_local_tool("buscar_en_base_de_conocimiento", {"consulta": "test"})
            self.assertIn("Búsqueda", lbl)
            self.assertEqual(content, "Contexto vacio")

    def test_normalize_tool_action(self):
        from gateway2.core.router_synthesizer import _normalize_tool_action
        # Variant 1: standard
        t, p = _normalize_tool_action({"herramienta": "foo", "parametros": {"a": 1}})
        self.assertEqual(t, "foo")
        self.assertEqual(p, {"a": 1})

        # Variant 2: OpenAI function calling style
        t, p = _normalize_tool_action({"name": "bar", "arguments": "{\"b\": 2}"})
        self.assertEqual(t, "bar")
        self.assertEqual(p, {"b": 2})

        # Variant 3: tool / action keys
        t, p = _normalize_tool_action({"tool": "baz", "params": {"c": 3}})
        self.assertEqual(t, "baz")
        self.assertEqual(p, {"c": 3})

        # Variant 4: string action
        t, p = _normalize_tool_action("simple_tool")
        self.assertEqual(t, "simple_tool")
        self.assertEqual(p, {})

    def test_explicit_pdf_when_slm_omits_or_renames_action(self):
        from gateway2.core.alignment_engine import UTILITY_TRIGGERS_PATTERN
        self.assertTrue(bool(UTILITY_TRIGGERS_PATTERN.search("Pasamelo en PDF")))
        self.assertTrue(bool(UTILITY_TRIGGERS_PATTERN.search("exportar a pdf")))

        data = {
            "messages": [
                {"role": "user", "content": "Bien juridico protegido"},
                {"role": "assistant", "content": "La vida humana es el bien mas protegido."},
                {"role": "user", "content": "Pasamelo en PDF"}
            ],
            "tools": [{"type": "function", "function": {"name": "generate_pdf_document"}}]
        }

        # Simular que el SLM devolvió clave "name" en vez de "herramienta"
        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Generar PDF",
            "acciones": [{"name": "generate_pdf_document", "arguments": {"title": "Bien Juridico"}}]
        }
        mock_card = "✅ Archivo PDF compilado exitosamente.\n[📥 Descargar doc.pdf](http://localhost/doc.pdf)"

        with patch("gateway2.core.router_synthesizer._call_router_slm", return_value=plan_resp), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", return_value=("Generación PDF: doc.pdf", mock_card)):

            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        last_content = res["messages"][-1]["content"]
        self.assertIn("INSTRUCCIÓN AL ASISTENTE (GENERACIÓN DE PDF)", last_content)
        self.assertIn("📥 Descargar doc.pdf", last_content)

    def test_cognitive_bridge_from_index_to_search(self):
        """Prueba que el puente cognitivo activa Hop 2 automáticamente si el Hop 1 devolvió sólo el índice."""
        data = {
            "messages": [
                {"role": "user", "content": "¿Cuál es el bien jurídico más protegido en el ordenamiento argentino?"}
            ],
            "tools": [
                {"type": "function", "function": {"name": "obtener_indice_biblioteca"}},
                {"type": "function", "function": {"name": "buscar_en_base_de_conocimiento"}}
            ]
        }

        # Hop 0: Planificador propone obtener_indice_biblioteca
        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Consultar catálogo de obras",
            "acciones": [{"herramienta": "obtener_indice_biblioteca", "parametros": {}}]
        }

        # Hop 1: Evaluador dice suficiente=False y siguiente_accion=None (callejón sin salida)
        eval_resp_hop1 = {
            "suficiente": False,
            "motivo": "El índice no contiene doctrinas literales",
            "siguiente_accion": None
        }

        # Hop 2: Evaluador tras la búsqueda semántica forzada por el puente
        eval_resp_hop2 = {
            "suficiente": True,
            "motivo": "Fragmento normativo encontrado",
            "siguiente_accion": None
        }

        with patch("gateway2.core.router_synthesizer._call_router_slm", side_effect=[plan_resp, eval_resp_hop1, eval_resp_hop2]), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", side_effect=[
                 ("Índice Biblioteca", "Catálogo de 91 obras..."),
                 ("Búsqueda Documental: bien juridico", "Artículo 84 Código Penal: Vida humana")
             ]):

            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        last_content = res["messages"][-1]["content"]
        self.assertIn("Artículo 84 Código Penal: Vida humana", last_content)
        self.assertIn("[INSTRUCCIÓN AL ASISTENTE]", last_content)
        self.assertNotIn("ABSTENCIÓN POR INSUFICIENCIA PROBATORIA", last_content)

    def test_cognitive_bridge_immune_to_injected_directive_crosstalk(self):
        """Verifica que si user_query contiene la palabra 'catálogo' dentro de la directiva inyectada, el puente no se suprima."""
        polluted_content = (
            "[CONSULTA ACTUAL DEL USUARIO]:\n"
            "¿Cuál es el bien jurídico más protegido en el ordenamiento argentino?\n\n"
            "[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]:\n"
            "Al tratarse de una consulta amplia, de catálogo, marco general o tratados, es OBLIGATORIO..."
        )
        data = {
            "messages": [{"role": "user", "content": polluted_content}],
            "tools": [{"type": "function", "function": {"name": "obtener_indice_biblioteca"}}]
        }

        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Índice",
            "acciones": [{"herramienta": "obtener_indice_biblioteca", "parametros": {}}]
        }
        eval_resp_hop1 = {"suficiente": False, "motivo": "Índice vacío de doctrina", "siguiente_accion": None}
        eval_resp_hop2 = {"suficiente": True, "motivo": "Doctrina encontrada", "siguiente_accion": None}

        with patch("gateway2.core.router_synthesizer._call_router_slm", side_effect=[plan_resp, eval_resp_hop1, eval_resp_hop2]), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", side_effect=[
                 ("Índice Biblioteca", "Catálogo..."),
                 ("Búsqueda Documental: bien juridico", "Vida humana Art 84")
             ]):

            res = asyncio.run(process_router_synthesizer(data))

        self.assertNotIn("tools", res)
        last_content = res["messages"][-1]["content"]
        self.assertIn("Vida humana Art 84", last_content)
        self.assertIn("[INSTRUCCIÓN AL ASISTENTE]", last_content)
        self.assertNotIn("[DIRECTIVA DE CONTROL", last_content)

    def test_summary_drilldown_from_search_to_read_document(self):
        """Verifica que si buscar_en_base_de_conocimiento devuelve un sumario con § X. Título, el puente profundiza con leer_documento_completo."""
        data = {
            "messages": [{"role": "user", "content": "¿Cuál es el bien jurídico más protegido?"}],
            "tools": [
                {"type": "function", "function": {"name": "buscar_en_base_de_conocimiento"}},
                {"type": "function", "function": {"name": "leer_documento_completo"}}
            ]
        }
        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Buscar doctrina",
            "acciones": [{"herramienta": "buscar_en_base_de_conocimiento", "parametros": {"consulta": "bien juridico"}}]
        }
        eval_hop1 = {"suficiente": False, "motivo": "Solo sumario", "siguiente_accion": None}
        eval_hop2 = {"suficiente": True, "motivo": "Sección leída", "siguiente_accion": None}

        search_out = (
            '--- FUENTE [1]: "Decreto 408/2026" [doc_id: 6a9f07f736300fe5f0afb9dd] ---\nTexto breve\n\n'
            '--- FUENTE [2]: "Derecho Penal Parte Especial" [doc_id: 6ada6fb0191007da2b3f4583] ---\n'
            'DELITOS CONTRA LAS PERSONAS § 6. Bienes jurídicos protegidos 5 VIII ÍNDICE GENERAL'
        )
        read_out = "DELITOS CONTRA LAS PERSONAS § 6. BIENES JURÍDICOS PROTEGIDOS: La vida humana y la integridad física..."

        with patch("gateway2.core.router_synthesizer._call_router_slm", side_effect=[plan_resp, eval_hop1, eval_hop2]), \
             patch("gateway2.core.router_synthesizer._execute_local_tool", side_effect=[
                 ("Búsqueda Documental", search_out),
                 ("Lectura Documento: 6ada6fb0191007da2b3f4583", read_out)
             ]) as mock_exec:

            res = asyncio.run(process_router_synthesizer(data))

        self.assertEqual(mock_exec.call_count, 2)
        second_call_args = mock_exec.call_args_list[1][0]
        self.assertEqual(second_call_args[0], "leer_documento_completo")
        self.assertEqual(second_call_args[1]["doc_id"], "6ada6fb0191007da2b3f4583")
        self.assertEqual(second_call_args[1]["seccion"], "§ 6. Bienes jurídicos protegidos")
        final_prompt = res["messages"][-1]["content"]
        self.assertIn("La vida humana y la integridad física", final_prompt)
        # El fragmento ruidoso del Hop 1 insuficiente debe haber sido descartado
        self.assertNotIn("Decreto 408/2026", final_prompt)
        # Verificar instrucciones de citación nominal y fidelidad de entidades
        self.assertIn("CITACIÓN NOMINAL OBLIGATORIA", final_prompt)
        self.assertIn("FIDELIDAD LITERAL DE ENTIDADES", final_prompt)

    def test_pdf_placeholder_title_deduced_cleanly(self):
        """Si el SLM envía 'Título representativo del contenido previo', debe deducir un título limpio sin acentos en el filename."""
        messages = [
            {"role": "user", "content": "¿Cuál es el bien jurídico que, según la doctrina, se protege con más fuerza?"},
            {"role": "assistant", "content": "El bien jurídico que recibe mayor protección es la **vida humana**, entendida como la integridad física y psíquica del ser humano en todas sus manifestaciones dentro del derecho penal argentino."},
            {"role": "user", "content": "pasamelo en PDF"}
        ]
        captured = {}

        def fake_create_pdf(title, markdown_content, filename):
            captured["title"] = title
            captured["filename"] = filename
            return {"download_url": f"http://127.0.0.1:8000/dl/{filename}", "filename": filename, "pages": 1, "size_kb": 2}

        with patch("pdf_engine.create_pdf_from_markdown", side_effect=fake_create_pdf):
            label, card = _execute_local_tool(
                "generate_pdf_document",
                {"title": "Título representativo del contenido previo"},
                messages=messages,
                user_query="pasamelo en PDF"
            )

        self.assertNotIn("representativo", captured["title"].lower())
        self.assertIn("Bien jurídico", captured["title"])
        self.assertIn("Vida Humana", captured["title"])
        self.assertEqual(captured["filename"], "bien_juridico_vida_humana.pdf")

    def test_external_tool_delegation_and_phase_b_synthesis(self):
        """
        Fase A: Una herramienta externa de Open-WebUI (ej. buscar_item) debe delegarse vía _delegated_tool_calls.
        Fase B: Al volver con role='tool', debe podar el mensaje 'tool' y sintetizar o abstenerse.
        """
        # --- Fase A ---
        data_phase_a = {
            "messages": [{"role": "user", "content": "Mostrame los datos del equipo de serie 2150087225AGRC018431"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "buscar_item",
                        "description": "Busca un equipo por serie",
                        "parameters": {
                            "type": "object",
                            "properties": {"termino": {"type": "string"}},
                            "required": ["termino"]
                        }
                    }
                }
            ]
        }
        plan_resp = {
            "requiere_herramientas": True,
            "plan": "Buscar equipo en inventario",
            "acciones": [{"herramienta": "buscar_item", "parametros": {"serie": "2150087225AGRC018431"}}]
        }
        with patch("gateway2.core.router_synthesizer._call_router_slm", return_value=plan_resp):
            res_a = asyncio.run(process_router_synthesizer(data_phase_a))

        self.assertIn("_delegated_tool_calls", res_a)
        self.assertEqual(res_a["_delegated_tool_calls"][0]["function"]["name"], "buscar_item")
        args_a = json.loads(res_a["_delegated_tool_calls"][0]["function"]["arguments"])
        self.assertEqual(args_a["termino"], "2150087225AGRC018431")

        # --- Fase B (con resultado no encontrado) ---
        data_phase_b = {
            "messages": [
                {"role": "user", "content": "Mostrame los datos del equipo de serie 2150087225AGRC018431"},
                {"role": "assistant", "content": None, "tool_calls": res_a["_delegated_tool_calls"]},
                {"role": "tool", "name": "buscar_item", "content": "No se encontraron resultados para 2150087225AGRC018431"}
            ],
            "tools": data_phase_a["tools"]
        }
        res_b = asyncio.run(process_router_synthesizer(data_phase_b))
        self.assertEqual(len(res_b["messages"]), 1)
        self.assertEqual(res_b["messages"][0]["role"], "user")
        self.assertIn("ABSTENCIÓN POR INSUFICIENCIA PROBATORIA", res_b["messages"][0]["content"])

    def test_web_search_deepseek_priority_and_ollama_fallback(self):
        """Verifica que perform_web_search prioriza DeepSeek cuando ambos están habilitados y cae en Ollama si DeepSeek devuelve vacío."""
        from gateway2.tools.web_search import perform_web_search

        def mock_env(key, default=""):
            if key in ("DEEPSEEK_SEARCH_ENABLED", "OLLAMA_SEARCH_ENABLED"):
                return "true"
            return default

        ds_hit = [{"title": "DeepSeek Result", "url": "https://ds.example", "content": "Contenido DS"}]
        ol_hit = [{"title": "Ollama Result", "url": "https://ol.example", "content": "Contenido OL"}]

        # Caso 1: DeepSeek responde con éxito -> No llama a Ollama
        with patch("gateway2.tools.web_search.get_env_setting", side_effect=mock_env), \
             patch("gateway2.tools.web_search.perform_deepseek_web_search", return_value=ds_hit) as m_ds, \
             patch("gateway2.tools.web_search.perform_ollama_web_search_direct", return_value=ol_hit) as m_ol:
            res1 = asyncio.run(perform_web_search("noticias hoy", 3))
            self.assertEqual(res1, ds_hit)
            self.assertEqual(m_ds.call_count, 1)
            self.assertEqual(m_ol.call_count, 0)

        # Caso 2: DeepSeek devuelve vacío -> Fallback automático a Ollama
        with patch("gateway2.tools.web_search.get_env_setting", side_effect=mock_env), \
             patch("gateway2.tools.web_search.perform_deepseek_web_search", return_value=[]) as m_ds, \
             patch("gateway2.tools.web_search.perform_ollama_web_search_direct", return_value=ol_hit) as m_ol:
            res2 = asyncio.run(perform_web_search("noticias hoy", 3))
            self.assertEqual(res2, ol_hit)
            self.assertEqual(m_ds.call_count, 1)
            self.assertEqual(m_ol.call_count, 1)


if __name__ == "__main__":
    unittest.main()
