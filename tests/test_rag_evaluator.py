import unittest
from unittest.mock import patch, MagicMock
import io
from rag.evaluator import evaluate_context_sufficiency, _extract_clean_json


class TestRagEvaluator(unittest.TestCase):

    def test_extract_clean_json(self):
        # 1. JSON puro
        raw = '{"suficiente": true, "motivo": "Todo claro", "faltantes": []}'
        res = _extract_clean_json(raw)
        self.assertEqual(res["suficiente"], True)

        # 2. JSON en markdown code fence
        md = "Aquí está el análisis:\n```json\n{\"suficiente\": false, \"motivo\": \"Falta artículo\", \"faltantes\": [\"artículo 2\"]}\n```"
        res2 = _extract_clean_json(md)
        self.assertEqual(res2["suficiente"], False)
        self.assertEqual(res2["faltantes"], ["artículo 2"])

        # 3. Texto con JSON embebido
        mixed = "Preámbulo {\"suficiente\": true, \"motivo\": \"ok\"} postfacio"
        res3 = _extract_clean_json(mixed)
        self.assertEqual(res3["suficiente"], True)

        # 4. JSON inválido
        self.assertIsNone(_extract_clean_json("no json here"))
        self.assertIsNone(_extract_clean_json(""))

    def test_empty_query_or_context(self):
        # Consulta vacía
        res1 = evaluate_context_sufficiency("", "contenido normativo")
        self.assertFalse(res1["suficiente"])
        self.assertEqual(res1["evaluador"], "vacio")

        # Contexto vacío
        res2 = evaluate_context_sufficiency("consulta", [])
        self.assertFalse(res2["suficiente"])
        self.assertEqual(res2["evaluador"], "vacio")

        # Contexto mensaje vacío
        res3 = evaluate_context_sufficiency("consulta", "No se encontraron fragmentos relevantes")
        self.assertFalse(res3["suficiente"])
        self.assertEqual(res3["evaluador"], "vacio")

    def test_fast_pass_heuristic(self):
        # Similitud alta (89%), puntuación limpia (punto final), consulta puntual
        res = evaluate_context_sufficiency(
            query="¿Cuál es la pena prevista para el homicidio simple?",
            context=[{"similarity": 0.89, "content": "Se impondrá reclusión de 8 a 25 años."}]
        )
        self.assertTrue(res["suficiente"])
        self.assertEqual(res["evaluador"], "fast_pass")
        self.assertIn("89%", res["motivo"])

    def test_fast_pass_bypassed_for_broad_query(self):
        # Similitud alta (89%) pero consulta de catálogo amplio: no debe hacer fast-pass
        # Al no estar disponible el puerto 18300 en el test, debe caer a fallback_heuristico
        res = evaluate_context_sufficiency(
            query="Pasame una lista de todos los tratados internacionales vigentes",
            context=[{"similarity": 0.89, "content": "Tratado Antártico."}]
        )
        self.assertNotEqual(res["evaluador"], "fast_pass")

    @patch("urllib.request.urlopen")
    def test_twil_lm3_evaluation_mock_sufficient(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "```json\\n{\\"suficiente\\": true, \\"motivo\\": \\"El texto define con precision el concepto demandado\\", \\"faltantes\\": []}\\n```"}}]}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = evaluate_context_sufficiency(
            query="Concepto de contrato de trabajo",
            context=[{"similarity": 0.65, "content": "Habrá contrato de trabajo siempre que una persona física se obligue..."}]
        )

        self.assertTrue(res["suficiente"])
        self.assertEqual(res["evaluador"], "twil-lm3")
        self.assertIn("define con precision", res["motivo"])

    @patch("urllib.request.urlopen")
    def test_twil_lm3_evaluation_mock_insufficient(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "{\\"suficiente\\": false, \\"motivo\\": \\"Solo se menciona el nombre del tratado pero no su articulado ni ratificacion\\", \\"faltantes\\": [\\"articulado\\", \\"ley ratificatoria\\"]}"}}]}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = evaluate_context_sufficiency(
            query="¿Cómo ratificó Argentina el tratado de no proliferación?",
            context=[{"similarity": 0.58, "content": "Tratado de no proliferación nuclear firmado en 1968"}]
        )

        self.assertFalse(res["suficiente"])
        self.assertEqual(res["evaluador"], "twil-lm3")
        self.assertIn("ley ratificatoria", res["faltantes"])

    @patch("urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_fallback_heuristic_when_backend_offline(self, mock_urlopen):
        # Similitud baja (52%), sin backend activo -> insuficiencia
        res = evaluate_context_sufficiency(
            query="Consulta compleja",
            context=[{"similarity": 0.52, "content": "Fragmento mínimo sin terminar"}]
        )
        self.assertFalse(res["suficiente"])
        self.assertEqual(res["evaluador"], "fallback_heuristico")


if __name__ == "__main__":
    unittest.main()
