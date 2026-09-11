"""
tests/test_rag_modular.py - Pruebas unitarias completas para el subsistema RAG modularizado (paquete rag/ y wrapper rag_engine.py).
Verifica:
1. Integridad de exportaciones y contratos 100% compatibles hacia atrás.
2. Esquema canónico PyArrow de LanceDB.
3. Normalización y expresiones regulares con límites seguros (Anti-Colisiones Romanas - Ley 4).
4. Particionado dinámico de chunks con tolerancia (±8%) y preservación de fronteras de sección.
5. Formateador de contexto RAG para LLM (alertas de vigencia, citas estructuradas, GPS hints).
6. Configuración de RAG y persistencia.
"""

import unittest
from unittest.mock import patch, MagicMock
import pyarrow as pa

import rag
import rag_engine
from rag.matching import normalize_text, build_boundary_regex, match_section_query
from rag.reader import _partition_chunks_dynamically
from rag.search import format_rag_context_for_llm
from rag.db import get_canonical_rag_schema
from rag.settings import get_rag_settings, save_rag_settings


class TestRagModularArchitecture(unittest.TestCase):
    """Verifica la arquitectura modular del paquete rag/ y su wrapper rag_engine."""

    def test_symbols_parity_between_package_and_wrapper(self):
        """Verifica que rag y rag_engine expongan exactamente los mismos símbolos."""
        pkg_all = set(rag.__all__)
        wrapper_all = set(rag_engine.__all__)
        self.assertEqual(pkg_all, wrapper_all, "Los símbolos exportados por rag y rag_engine deben ser idénticos")
        self.assertGreaterEqual(len(pkg_all), 30, "Deben exportarse al menos 30 símbolos canónicos del subsistema RAG")

        # Verificar que todos los atributos existan en ambos módulos
        for symbol in pkg_all:
            self.assertTrue(hasattr(rag, symbol), f"El paquete rag debe contener {symbol}")
            self.assertTrue(hasattr(rag_engine, symbol), f"rag_engine debe re-exportar {symbol}")
            # Deben ser idénticos por referencia
            self.assertIs(getattr(rag, symbol), getattr(rag_engine, symbol))

    def test_canonical_schema_fields(self):
        """Verifica el esquema canónico oficial PyArrow para LanceDB."""
        schema = get_canonical_rag_schema()
        self.assertIsInstance(schema, pa.Schema)
        expected_fields = [
            "id", "doc_id", "doc_title", "doc_author", "doc_topic",
            "doc_date", "section_path", "chunk_index", "chunk_tokens",
            "total_chunks", "total_doc_tokens", "content", "text",
            "vector", "doc_vigencia", "doc_fecha_publicacion"
        ]
        actual_fields = schema.names
        for field_name in expected_fields:
            self.assertIn(field_name, actual_fields, f"El esquema debe contener el campo {field_name}")

        # Vector de 1024 dimensiones
        vector_field = schema.field("vector")
        self.assertTrue(pa.types.is_fixed_size_list(vector_field.type))
        self.assertEqual(vector_field.type.list_size, 1024)
        self.assertEqual(vector_field.type.value_type, pa.float32())


class TestRagMatchingEngine(unittest.TestCase):
    """Verifica las funciones matemáticas y analíticas de coincidencia en rag/matching.py (Ley 4)."""

    def test_normalize_text(self):
        """Verifica la eliminación de acentos, minúsculas y espacios colapsados."""
        self.assertEqual(normalize_text("  Código   Penal  "), "codigo penal")
        self.assertEqual(normalize_text("Constitución Nacional"), "constitucion nacional")
        self.assertEqual(normalize_text("Título I: Delitos"), "titulo i: delitos")
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")

    def test_build_boundary_regex(self):
        """Verifica la generación de regex con límites de palabra seguros en bordes alfanuméricos."""
        regex_str = build_boundary_regex("titulo i")
        self.assertTrue(regex_str.startswith(r"(?:\b|^)"))
        self.assertTrue(regex_str.endswith(r"(?:\b|$)"))
        self.assertEqual(build_boundary_regex(""), "")

    def test_match_section_query_roman_numerals_no_collision(self):
        """
        Ley 4: Verifica que 'titulo i' NO coincida falsamente con 'titulo ii', 'titulo ix' ni 'titulo iv'.
        """
        self.assertFalse(match_section_query("titulo i", "TITULO II - DE LAS PENAS"))
        self.assertFalse(match_section_query("titulo i", "TITULO IX - DELITOS CONTRA LA SEGURIDAD"))
        self.assertFalse(match_section_query("titulo i", "TITULO IV - DISPOSICIONES"))
        self.assertTrue(match_section_query("titulo i", "TITULO I - DELITOS CONTRA LAS PERSONAS"))
        self.assertTrue(match_section_query("titulo ii", "TITULO II - DE LAS PENAS"))

    def test_match_section_query_composite_hierarchy(self):
        """Verifica consultas compuestas como 'Libro II Titulo I' o 'Titulo I del Libro II'."""
        target = "Libro II > Titulo I - Delitos contra las personas"
        self.assertTrue(match_section_query("Libro II Titulo I", target))
        self.assertTrue(match_section_query("Titulo I del Libro II", target))
        self.assertTrue(match_section_query("Libro II > Titulo I", target))
        self.assertTrue(match_section_query("Delitos contra las personas", target))
        self.assertFalse(match_section_query("Libro I Titulo I", target))

    def test_match_section_query_abbreviations(self):
        """Verifica equivalencia de abreviaturas normativas (art. vs articulo)."""
        target = "Codigo Civil y Comercial > Articulo 75"
        self.assertTrue(match_section_query("art. 75", target))
        self.assertTrue(match_section_query("articulo 75", target))
        self.assertTrue(match_section_query("Art. 75", target))


class TestRagReaderPartitioning(unittest.TestCase):
    """Verifica el particionado dinámico de chunks con preservación de fronteras de sección."""

    def test_dynamic_partitioning_preserves_section_boundaries(self):
        """Verifica que _partition_chunks_dynamically corte en cambios de sección dentro de la tolerancia."""
        # 8 chunks: 4 de la Seccion A (100 tokens c/u), 4 de la Seccion B (100 tokens c/u)
        chunks = [
            ("id_1", "Seccion A", "Contenido 1", 100),
            ("id_2", "Seccion A", "Contenido 2", 100),
            ("id_3", "Seccion A", "Contenido 3", 100),
            ("id_4", "Seccion A", "Contenido 4", 100),
            ("id_5", "Seccion B", "Contenido 5", 100),
            ("id_6", "Seccion B", "Contenido 6", 100),
            ("id_7", "Seccion B", "Contenido 7", 100),
            ("id_8", "Seccion B", "Contenido 8", 100),
        ]
        # Target: 420 tokens, tolerancia 8% -> min 386 tokens, max 453 tokens.
        # Al llegar al chunk 4 (400 tokens), el siguiente chunk cambia a "Seccion B",
        # y 400 >= 386, por lo que corta limpiamente al final de Seccion A.
        # La Seccion B acumula 400 tokens (< 453) y se entrega en la parte 2.
        partes = _partition_chunks_dynamically(chunks, target_tokens=420, tolerance_pct=0.08)
        self.assertEqual(len(partes), 2)
        part_1_items, part_1_toks = partes[0]
        part_2_items, part_2_toks = partes[1]
        self.assertEqual(len(part_1_items), 4)
        self.assertEqual(part_1_toks, 400)
        self.assertEqual(len(part_2_items), 4)
        self.assertEqual(part_2_toks, 400)


class TestRagSearchFormatting(unittest.TestCase):
    """Verifica el formateo estructurado de contexto para el LLM."""

    def test_format_rag_context_empty(self):
        """Verifica mensaje canónico cuando no hay resultados."""
        result = format_rag_context_for_llm([])
        self.assertIn("No se encontraron fragmentos relevantes", result)

    def test_format_rag_context_with_vigencia_alerts(self):
        """Verifica inyección de alertas críticas de vigencia (derogada, proyecto, etc.)."""
        mock_results = [
            {
                "doc_title": "Ley Antigua",
                "doc_id": "ley_antigua",
                "doc_topic": "Derecho",
                "doc_vigencia": "derogado",
                "doc_fecha_publicacion": "1990-01-01",
                "section_path": "Capítulo I",
                "doc_author": "Congreso",
                "content": "Texto de norma derogada.",
                "similarity": 0.88,
                "chunk_tokens": 50,
                "total_doc_tokens": 5000,
                "total_chunks": 20
            }
        ]
        formatted = format_rag_context_for_llm(mock_results)
        self.assertIn("⚠️ [Aviso Crítico de Vigencia]: Esta norma se encuentra DEROGADA", formatted)
        self.assertIn("Vigencia: DEROGADO", formatted)
        self.assertIn("doc_id: ley_antigua", formatted)

    def test_format_rag_context_extensive_work_action_hint(self):
        """Verifica sugerencia de GPS Documental para obras extensas (> 30.000 tokens)."""
        mock_results = [
            {
                "doc_title": "Código Civil Extenso",
                "doc_id": "ccycn",
                "doc_topic": "Derecho",
                "doc_vigencia": "vigente",
                "doc_fecha_publicacion": "2015-08-01",
                "section_path": "Libro Primero > Titulo Preliminar",
                "doc_author": "Congreso",
                "content": "Artículos preliminares...",
                "similarity": 0.95,
                "chunk_tokens": 120,
                "total_doc_tokens": 150000,
                "total_chunks": 500
            }
        ]
        formatted = format_rag_context_for_llm(mock_results)
        self.assertIn("💡 [Acción Disponible (Obra Extensa ~150,000 tokens)]:", formatted)
        self.assertIn("obtener_estructura_documento(doc_id=\"ccycn\")", formatted)
        self.assertIn("leer_documento_completo(doc_id=\"ccycn\", seccion=\"Titulo Preliminar\")", formatted)


class TestRagSettings(unittest.TestCase):
    """Verifica la persistencia y lectura de configuraciones RAG."""

    @patch("rag.settings.get_mongo_db")
    def test_get_rag_settings_default_fallback(self, mock_db_getter):
        """Verifica retorno de valores por defecto cuando MongoDB no tiene doc global o falla."""
        mock_db = MagicMock()
        mock_db.rag_settings.find_one.return_value = None
        mock_db_getter.return_value = mock_db

        settings = get_rag_settings()
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["active_topics"], [])
        self.assertEqual(settings["cloud_rag_provider_id"], "")

    @patch("rag.settings.get_mongo_db")
    def test_save_rag_settings_updates_mongo(self, mock_db_getter):
        """Verifica actualización correcta en MongoDB."""
        mock_db = MagicMock()
        mock_db_getter.return_value = mock_db

        ok = save_rag_settings(
            active_topics=["Derecho Penal"],
            enabled=True,
            cloud_rag_provider_id="openrouter",
            cloud_rag_provider_name="OpenRouter",
            cloud_rag_model_id="anthropic/claude-3.5-sonnet"
        )
        self.assertTrue(ok)
        mock_db.rag_settings.update_one.assert_called_once()
        args, kwargs = mock_db.rag_settings.update_one.call_args
        self.assertEqual(args[0], {"_id": "global"})
        set_dict = args[1]["$set"]
        self.assertEqual(set_dict["active_topics"], ["Derecho Penal"])
        self.assertTrue(set_dict["enabled"])
        self.assertEqual(set_dict["cloud_rag_provider_id"], "openrouter")


if __name__ == "__main__":
    unittest.main()
