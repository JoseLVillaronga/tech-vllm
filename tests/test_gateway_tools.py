import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from gateway.tools.web_search import get_env_setting
from gateway.cloud.cloud_sync import slugify_provider_name
from gateway.cloud.cloud_router import resolve_cloud_model


class TestGatewayToolsAndCloud(unittest.IsolatedAsyncioTestCase):

    def test_slugify_provider_name(self):
        self.assertEqual(slugify_provider_name("Groq Cloud (US)"), "groq_cloud_us")
        self.assertEqual(slugify_provider_name("OpenRouter AI"), "openrouter_ai")
        self.assertEqual(slugify_provider_name("   "), "cloud")

    def test_get_env_setting(self):
        val = get_env_setting("OLLAMA_SEARCH_MAX_RESULTS", "3")
        self.assertIsNotNone(val)

    async def test_resolve_local_model(self):
        is_cloud, model, prov, rag_inj, base_m = await resolve_cloud_model("local/google/gemma-4-E4B-it", "test-key", None)
        self.assertFalse(is_cloud)
        self.assertEqual(model, "google/gemma-4-E4B-it")
        self.assertFalse(rag_inj)

    async def test_resolve_rag_virtual_model(self):
        is_cloud, model, prov, rag_inj, base_m = await resolve_cloud_model("gemma-4-rag", "test-key", None)
        self.assertFalse(is_cloud)
        self.assertEqual(model, "gemma-4-rag")
        self.assertTrue(rag_inj)

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("os.path.isfile")
    @patch("os.path.getmtime")
    def test_handle_pdf_download_variants(self, mock_mtime, mock_isfile, mock_listdir, mock_exists):
        from gateway.tools.pdf_generator import handle_pdf_download
        mock_exists.return_value = True
        mock_listdir.return_value = ["a1b2c3d4e5f6_contrato.pdf"]
        mock_isfile.return_value = True
        mock_mtime.return_value = 1000.0

        # Probando variante de 2 parámetros
        res_2params = handle_pdf_download("a1b2c3d4e5f6", "contrato.pdf")
        self.assertEqual(res_2params.filename, "contrato.pdf")

        # Probando variante de 1 parámetro (sólo filename)
        res_1param = handle_pdf_download("contrato.pdf", "contrato.pdf")
        self.assertEqual(res_1param.filename, "contrato.pdf")

    def test_clean_latex_degree_and_symbols(self):
        from pdf_engine import clean_latex, sanitize_text_for_pdf
        self.assertEqual(clean_latex(r"meta 1.5^{\circ}C"), "meta 1.5°C")
        self.assertEqual(clean_latex(r"$1.5^\circ \text{C}$"), "1.5° C")
        self.assertEqual(clean_latex(r"$\text{CO}_2$"), "CO2")
        self.assertEqual(clean_latex(r"10 \pm 2"), "10 ± 2")
        self.assertEqual(sanitize_text_for_pdf(r"meta 1.5^{\circ}\text{C}"), "meta 1.5°C")

    def test_pdf_table_generation(self):
        from pdf_engine import create_pdf_from_markdown
        md = """# Documento de Soporte
| Tipo de Acción | Soporte Mesas | Redes |
| :--- | :--- | :--- |
| ASC (Ciclo Corto) | <= 2 min | <= 10 min |
| ASE (Ciclo Extendido) | Repuesto | Equipos |
"""
        res = create_pdf_from_markdown(title="Prueba Tablas", markdown_content=md, filename="test_table.pdf")
        self.assertTrue(res["success"])
    def test_clean_markdown_inline_and_bullets(self):
        from pdf_engine import clean_markdown_inline, sanitize_text_for_pdf, PDFDocumentBuilder
        self.assertEqual(clean_markdown_inline("**ASC** (Ciclo Corto)"), "ASC (Ciclo Corto)")
        self.assertEqual(clean_markdown_inline("**Redes:** < 10 min. **Equipos:** < 2 min."), "Redes: < 10 min. Equipos: < 2 min.")
        self.assertEqual(clean_markdown_inline("`código` y __subrayado__"), "código y subrayado")
        
        # Probar builder con tabla conteniendo markdown y listas con asteriscos
        builder = PDFDocumentBuilder(company_name="Prueba Markdown")
        md_text = """# Resumen Ejecutivo
| Tipo de Acción | Alcance | Duración |
| :--- | :--- | :--- |
| **ASC** (Ciclo Corto) | Individual | **Redes:** < 10 min. |
| **ASE** (Ciclo Extendido) | Individual | Reemplazo |

## Roles
* Responsable de Soporte: Ejecuta.
  * Colaborador: Atiende.
"""
        builder.render_markdown(md_text, title="Resumen")
        pdf_bytes = builder.build_pdf()
        self.assertGreater(len(pdf_bytes), 500)


    def test_rag_document_structure_and_gps(self):
        from rag_engine import get_document_structure
        res = get_document_structure("Constitución Nacional Argentina")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("titulo"), "Constitución Nacional Argentina")
        self.assertGreater(res.get("sections_count", 0), 10)
        self.assertIn("GPS Documental", res.get("content", ""))
        self.assertIn("Preámbulo", res.get("content", ""))

    def test_rag_document_section_retrieval(self):
        from rag_engine import get_document_full_content
        # Prueba con sección específica
        res = get_document_full_content("Constitución Nacional Argentina", seccion="Nuevos derechos")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("modo"), "seccion_focalizada")
        self.assertIn("Artículo 36", res.get("content", ""))

        # Prueba con sección inexistente (debe retornar sugerencias amigables)
        bad_res = get_document_full_content("Constitución Nacional Argentina", seccion="Sección Inexistente XYZ")
        self.assertFalse(bad_res.get("success"))
        self.assertIn("Secciones principales disponibles", bad_res.get("error", ""))

    def test_rag_dynamic_tolerance_partitioning(self):
        from rag_engine import _partition_chunks_dynamically
        # Simular chunks de 3 secciones
        chunks = [
            ("ch1", "Sec A", "Párrafo A1", 4000),
            ("ch2", "Sec A", "Párrafo A2", 4000),
            ("ch3", "Sec B", "Párrafo B1", 4000), # Total acumulado 12000 (cerca de target 10000 con +8% tolerance)
            ("ch4", "Sec B", "Párrafo B2", 4000),
            ("ch5", "Sec C", "Párrafo C1", 4000)
        ]
        # Target 10.000 con tolerance 0.20 (rango 8.000 - 12.000)
        partes = _partition_chunks_dynamically(chunks, target_tokens=10000, tolerance_pct=0.25)
        self.assertGreaterEqual(len(partes), 2)
        # La primera parte debe contener ch1 y ch2 (8.000 tokens en corte de sección A -> B)
        self.assertEqual(len(partes[0][0]), 2)
        self.assertEqual(partes[0][1], 8000)

    def test_rag_vigencia_proactive_alert(self):
        from rag_engine import format_rag_context_for_llm
        mock_derogado = [{
            "doc_title": "Ley Histórica de Prueba",
            "doc_id": "test_derogado_123",
            "doc_topic": "Derecho",
            "doc_vigencia": "derogado",
            "doc_fecha_publicacion": "1900-01-01",
            "section_path": "Capítulo I",
            "content": "Texto de norma derogada",
            "similarity": 0.85
        }]
        out = format_rag_context_for_llm(mock_derogado)
        self.assertIn("Aviso Crítico de Vigencia", out)
        self.assertIn("DEROGADA", out)
        self.assertIn("Vigencia: DEROGADO", out)

    def test_rag_library_index_generation(self):
        from rag_engine import get_library_index
        res = get_library_index()
        self.assertTrue(res.get("success"))
        self.assertGreater(res.get("total_documents", 0), 0)
        self.assertIn("Mapa Ontológico Global", res.get("content", ""))


if __name__ == "__main__":
    unittest.main()

