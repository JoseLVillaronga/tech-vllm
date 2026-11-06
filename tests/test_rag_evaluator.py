import unittest
from unittest.mock import patch, MagicMock
import io
import json
from rag.evaluator import evaluate_context_sufficiency, _extract_clean_json, _is_rwkv_evaluator


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

        with patch.dict("os.environ", {"EVALUATOR_MODEL": "$LLAMA_DIR/models/twil-lm3-q4_k_m.gguf", "EVALUATOR_ALIAS": "twil-lm3-q4_k_m"}):
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

        with patch.dict("os.environ", {"EVALUATOR_MODEL": "$LLAMA_DIR/models/twil-lm3-q4_k_m.gguf", "EVALUATOR_ALIAS": "twil-lm3-q4_k_m"}):
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


    def test_is_rwkv_evaluator_detection(self):
        # twil-lm3
        with patch.dict("os.environ", {"EVALUATOR_MODEL": "$LLAMA_DIR/models/twil-lm3-q4_k_m.gguf", "EVALUATOR_ALIAS": "twil-lm3-q4_k_m"}):
            self.assertFalse(_is_rwkv_evaluator())

        # Finch 7B
        with patch.dict("os.environ", {"EVALUATOR_MODEL": "$LLAMA_DIR/models/v6-Finch-7B-HF-Q5_K_M.gguf", "EVALUATOR_ALIAS": "v6-Finch-7B"}):
            self.assertTrue(_is_rwkv_evaluator())

        # RWKV-6 genérico
        with patch.dict("os.environ", {"EVALUATOR_MODEL": "/models/RWKV-v6-World-7B.gguf", "EVALUATOR_ALIAS": ""}):
            self.assertTrue(_is_rwkv_evaluator())

    @patch("urllib.request.urlopen")
    def test_rwkv_evaluation_mock_sufficient(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"content": " SI\\n\\n"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict("os.environ", {"EVALUATOR_MODEL": "$LLAMA_DIR/models/v6-Finch-7B-HF-Q5_K_M.gguf"}):
            res = evaluate_context_sufficiency(
                query="Concepto de contrato de trabajo",
                context=[{"similarity": 0.65, "content": "Habrá contrato de trabajo siempre que una persona física se obligue..."}]
            )

        self.assertTrue(res["suficiente"])
        self.assertEqual(res["evaluador"], "rwkv-finch")
        self.assertEqual(res["faltantes"], [])
        self.assertIn("suficiente y concluyente", res["motivo"])

    @patch("urllib.request.urlopen")
    def test_rwkv_evaluation_mock_insufficient(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"content": " NO\\n\\n"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict("os.environ", {"EVALUATOR_MODEL": "$LLAMA_DIR/models/v6-Finch-7B-HF-Q5_K_M.gguf"}):
            res = evaluate_context_sufficiency(
                query="¿Cómo ratificó Argentina el tratado de no proliferación?",
                context=[{"similarity": 0.58, "content": "Tratado de no proliferación nuclear firmado en 1968"}]
            )

        self.assertFalse(res["suficiente"])
        self.assertEqual(res["evaluador"], "rwkv-finch")
        self.assertIn("insuficiente o incompleta", res["motivo"])
        self.assertIn("información específica o articulado dispositivo", res["faltantes"])

    @patch("urllib.request.urlopen")
    def test_twil_custom_max_chars_ingestion_complete_when_below_threshold(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "{\\"suficiente\\": true, \\"motivo\\": \\"Completo\\"}"}}]}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # 14.500 caracteres de contexto con umbral de 15.000
        long_content = "X" * 14500
        with patch.dict("os.environ", {
            "EVALUATOR_MODEL": "$LLAMA_DIR/models/twil-lm3-q4_k_m.gguf",
            "EVALUATOR_ALIAS": "twil-lm3-q4_k_m",
            "EVALUATOR_TWIL_MAX_CHARS": "15000"
        }):
            res = evaluate_context_sufficiency(
                query="Consulta doctrinaria",
                context=long_content
            )

        self.assertTrue(res["suficiente"])
        # Verificar que el payload enviado a urlopen contenga el texto completo sin elipsis '[...]'
        call_args = mock_urlopen.call_args[0]
        req_body = json.loads(call_args[0].data.decode("utf-8"))
        user_msg = req_body["messages"][1]["content"]
        self.assertNotIn("[...]", user_msg)
        self.assertIn(long_content, user_msg)

    @patch("urllib.request.urlopen")
    def test_twil_custom_max_chars_ingestion_truncated_when_above_threshold(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"choices": [{"message": {"content": "{\\"suficiente\\": true, \\"motivo\\": \\"Truncado\\"}"}}]}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # 20.000 caracteres de contexto con umbral de 15.000
        prefix = "A" * 4500
        middle = "B" * 5000
        suffix = "C" * 10500
        long_content = prefix + middle + suffix  # 20.000 chars

        with patch.dict("os.environ", {
            "EVALUATOR_MODEL": "$LLAMA_DIR/models/twil-lm3-q4_k_m.gguf",
            "EVALUATOR_ALIAS": "twil-lm3-q4_k_m",
            "EVALUATOR_TWIL_MAX_CHARS": "15000"
        }):
            res = evaluate_context_sufficiency(
                query="Consulta doctrinaria",
                context=long_content
            )

        self.assertTrue(res["suficiente"])
        call_args = mock_urlopen.call_args[0]
        req_body = json.loads(call_args[0].data.decode("utf-8"))
        user_msg = req_body["messages"][1]["content"]
        self.assertIn("[...]", user_msg)
        self.assertIn(prefix, user_msg)
        self.assertIn(suffix, user_msg)
        self.assertNotIn(middle, user_msg)


if __name__ == "__main__":
    unittest.main()
