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
        self.assertGreater(res["size_kb"], 0)


if __name__ == "__main__":
    unittest.main()
