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
        res = get_document_structure("CONSTITUCION DE LA NACION ARGENTINA Ley Nº 24.430")
        self.assertTrue(res.get("success"))
        self.assertIn("CONSTITUCION", res.get("titulo", "").upper())
        self.assertGreater(res.get("sections_count", 0), 5)
        self.assertIn("GPS Documental", res.get("content", ""))

    def test_rag_document_section_retrieval(self):
        from rag_engine import get_document_full_content
        # Prueba con sección específica
        res = get_document_full_content("CONSTITUCION DE LA NACION ARGENTINA Ley Nº 24.430", seccion="ARTÍCULO 75")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("modo"), "seccion_focalizada")
        self.assertIn("Corresponde al Congreso", res.get("content", ""))

        # Prueba con sección inexistente (debe retornar sugerencias amigables)
        bad_res = get_document_full_content("CONSTITUCION DE LA NACION ARGENTINA Ley Nº 24.430", seccion="Sección Inexistente XYZ")
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

    def test_optimize_image_resolution_for_vit(self):
        import io
        import base64
        from PIL import Image
        from gateway.tools.vision import optimize_image_resolution_for_vit

        def make_data_uri(w, h):
            img = Image.new("RGB", (w, h), color=(200, 200, 200))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{b64}"

        def get_uri_size(uri):
            payload = uri.split(";base64,")[1]
            img = Image.open(io.BytesIO(base64.b64decode(payload)))
            return img.size

        # 1. Imagen chica (107x193): debe reescalar por dimensión y área
        small_uri = make_data_uri(107, 193)
        resized_uri = optimize_image_resolution_for_vit(small_uri, min_dimension=512, min_area=512*512)
        rw, rh = get_uri_size(resized_uri)
        self.assertGreaterEqual(min(rw, rh), 512)
        self.assertGreaterEqual(rw * rh, 512 * 512)

        # 2. Imagen panorámica con área chica (512x200): área 102.400 < 262.144 -> debe reescalar por área
        pano_uri = make_data_uri(512, 200)
        resized_pano = optimize_image_resolution_for_vit(pano_uri, min_dimension=512, min_area=512*512)
        pw, ph = get_uri_size(resized_pano)
        self.assertGreaterEqual(pw * ph, 512 * 512)

        # 3. Imagen grande (800x800): no debe modificarse
        big_uri = make_data_uri(800, 800)
        unchanged_uri = optimize_image_resolution_for_vit(big_uri, min_dimension=512, min_area=512*512)
        bw, bh = get_uri_size(unchanged_uri)
        self.assertEqual((bw, bh), (800, 800))


    def test_section_matching_roman_and_hierarchy(self):
        from rag_engine import match_section_query

        s_l1_t1 = "Codigo Penal Argentino > LIBRO PRIMERO (LIBRO I) - DISPOSICIONES GENERALES > TITULO I (TÍTULO 1) - APLICACION DE LA LEY PENAL > ARTÍCULO 1°"
        s_l1_t2 = "Codigo Penal Argentino > LIBRO PRIMERO (LIBRO I) - DISPOSICIONES GENERALES > TITULO II (TÍTULO 2) - DE LAS PENAS > ARTÍCULO 5°"
        s_l1_t4 = "Codigo Penal Argentino > LIBRO PRIMERO (LIBRO I) - DISPOSICIONES GENERALES > TITULO IV (TÍTULO 4) - REPARACION > ARTÍCULO 29°"
        s_l1_t9 = "Codigo Penal Argentino > LIBRO PRIMERO (LIBRO I) - DISPOSICIONES GENERALES > TITULO IX (TÍTULO 9) - CONCURSO > ARTÍCULO 54°"
        s_l1_t12 = "Codigo Penal Argentino > LIBRO PRIMERO (LIBRO I) - DISPOSICIONES GENERALES > TITULO XII (TÍTULO 12) - SUSPENSION > ARTÍCULO 76°"
        s_l2_t1 = "Codigo Penal Argentino > LIBRO SEGUNDO (LIBRO II) - DE LOS DELITOS > TITULO I (TÍTULO 1) - DELITOS CONTRA LAS PERSONAS > ARTÍCULO 79° - -** Se aplicará"
        s_l2_t2 = "Codigo Penal Argentino > LIBRO SEGUNDO (LIBRO II) - DE LOS DELITOS > TITULO II (TÍTULO 2) - DELITOS CONTRA EL HONOR > ARTÍCULO 109°"

        # 1. 'TITULO I' no debe colisionar con TITULO II, IV, IX, XII
        self.assertTrue(match_section_query("TITULO I", s_l1_t1))
        self.assertTrue(match_section_query("TITULO I", s_l2_t1))
        self.assertFalse(match_section_query("TITULO I", s_l1_t2))
        self.assertFalse(match_section_query("TITULO I", s_l1_t4))
        self.assertFalse(match_section_query("TITULO I", s_l1_t9))
        self.assertFalse(match_section_query("TITULO I", s_l1_t12))
        self.assertFalse(match_section_query("TITULO I", s_l2_t2))

        # 2. 'LIBRO I' vs 'LIBRO II'
        self.assertTrue(match_section_query("LIBRO I", s_l1_t1))
        self.assertFalse(match_section_query("LIBRO I", s_l2_t1))
        self.assertTrue(match_section_query("LIBRO II", s_l2_t1))
        self.assertFalse(match_section_query("LIBRO II", s_l1_t1))

        # 3. Consultas compuestas jerárquicas
        self.assertTrue(match_section_query("Libro II Titulo I", s_l2_t1))
        self.assertFalse(match_section_query("Libro II Titulo I", s_l1_t1))
        self.assertTrue(match_section_query("Titulo I del Libro II", s_l2_t1))
        self.assertFalse(match_section_query("Titulo I del Libro II", s_l1_t1))

        # 4. Denominación temática
        self.assertTrue(match_section_query("Delitos contra las personas", s_l2_t1))
        self.assertFalse(match_section_query("Delitos contra las personas", s_l2_t2))

        # 5. Abreviaturas normativas (art. 79 vs ARTÍCULO 79°)
        self.assertTrue(match_section_query("art. 79", s_l2_t1))
        self.assertTrue(match_section_query("articulo 79", s_l2_t1))
        self.assertFalse(match_section_query("art. 80", s_l2_t1))

    def test_pdf_filename_sanitization_and_slashes(self):
        from pdf_engine import sanitize_pdf_filename, create_pdf_from_markdown

        # 1. Título con barras (ej: Decreto 1030/2020) no debe contener / en el filename resultante
        fname_decreto = sanitize_pdf_filename(None, fallback_title="Decreto 1030/2020")
        self.assertEqual(fname_decreto, "decreto_1030_2020.pdf")

        # 2. Filename explícito con barras y espacios
        fname_explicit = sanitize_pdf_filename("ley/27.520 y decreto 1030/2020.pdf")
        self.assertEqual(fname_explicit, "ley_27.520_y_decreto_1030_2020.pdf")
        self.assertNotIn("/", fname_explicit)
        self.assertNotIn("\\", fname_explicit)

        # 3. Path traversal intento ../../etc/passwd
        fname_traversal = sanitize_pdf_filename("../../etc/passwd")
        self.assertEqual(fname_traversal, "etc_passwd.pdf")
        self.assertNotIn("/", fname_traversal)
        self.assertNotIn("..", fname_traversal)

        # 4. Creación real de PDF con título con barras inclinadas (Decreto 1030/2020) sin Errno 2
        res = create_pdf_from_markdown(
            title="Análisis del Decreto 1030/2020",
            markdown_content="# Análisis\n\nTexto de prueba.",
            filename=None
        )
        self.assertTrue(res["success"])
        self.assertNotIn("/", res["filename"])
        self.assertTrue(res["filename"].endswith(".pdf"))
        self.assertIn("1030_2020", res["filename"])
        import os
        self.assertTrue(os.path.exists(res["file_path"]))


if __name__ == "__main__":
    unittest.main()



