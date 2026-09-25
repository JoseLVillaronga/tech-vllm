"""
tests/test_gateway_models_contract.py - Pruebas unitarias para el contrato de /v1/models y enrutamiento en Gateway.
Verifica que el campo 'id' sea un slug limpio sin caracteres especiales y que 'name' contenga el alias descriptivo.
"""

import os
import json
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from gateway.cloud.cloud_router import handle_models_list, resolve_cloud_model


class TestGatewayModelsContract(unittest.IsolatedAsyncioTestCase):
    """Pruebas de compatibilidad con OpenAI y Open-WebUI para /v1/models."""

    @patch("gateway.cloud.cloud_router.httpx.AsyncClient")
    async def test_handle_models_list_clean_id_and_display_name(self, mock_client_cls):
        """Verifica que /v1/models devuelva id limpio y name descriptivo cuando llama-server retorna ambos."""
        # Mock de respuesta de llama-server /v1/models
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "object": "list",
            "data": [
                {
                    "id": "CorpAI-Gen",
                    "object": "model",
                    "created": 1727280000,
                    "owned_by": "llamacpp",
                    "aliases": ["CorpAI-Gen", "CorpAI-Gen | Legal & Compliance"]
                }
            ],
            "models": [
                {
                    "name": "CorpAI-Gen | Legal & Compliance",
                    "model": "CorpAI-Gen | Legal & Compliance"
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__.return_value = mock_client
        mock_client_cls.return_value = mock_client

        token = "test-token"
        key_doc = {"_id": "test_id", "services": ["gemma"], "allowed_providers": []}

        with patch("gateway.cloud.cloud_router.get_db") as mock_db:
            mock_db.return_value.api_key_models.find.return_value = []
            resp = await handle_models_list(token, key_doc, current_target_port=18100)
        self.assertEqual(resp.status_code, 200)

        body = json.loads(resp.body.decode("utf-8"))
        self.assertIn("data", body)
        self.assertIn("models", body)

        local_model = next((m for m in body["data"] if m["id"] == "local/CorpAI-Gen"), None)
        self.assertIsNotNone(local_model)
        self.assertEqual(local_model["id"], "local/CorpAI-Gen")
        self.assertEqual(local_model["name"], "local/CorpAI-Gen | Legal & Compliance")
        self.assertIn("local/CorpAI-Gen | Legal & Compliance", local_model["aliases"])

        # Verificar formato Ollama
        ollama_model = next((m for m in body["models"] if m["model"] == "local/CorpAI-Gen"), None)
        self.assertIsNotNone(ollama_model)
        self.assertEqual(ollama_model["name"], "local/CorpAI-Gen | Legal & Compliance")

    @patch("gateway.cloud.cloud_router.httpx.AsyncClient")
    async def test_handle_models_list_fallback_when_raw_id_has_special_chars(self, mock_client_cls):
        """Verifica saneamiento automático si llama-server devuelve ID con espacios o pipes."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "object": "list",
            "data": [
                {
                    "id": "CorpAI-Gen | Legal & Compliance",
                    "object": "model",
                    "created": 1727280000,
                    "owned_by": "llamacpp"
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__.return_value = mock_client
        mock_client_cls.return_value = mock_client

        token = "test-token"
        key_doc = {"_id": "test_id", "services": ["gemma"], "allowed_providers": []}

        with patch.dict(os.environ, {"LLAMA_MODEL_ID": "CorpAI-Gen", "LLAMA_ALIAS": "CorpAI-Gen | Legal & Compliance"}), \
             patch("gateway.cloud.cloud_router.get_db") as mock_db:
            mock_db.return_value.api_key_models.find.return_value = []
            resp = await handle_models_list(token, key_doc, current_target_port=18100)
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.body.decode("utf-8"))

            local_model = next((m for m in body["data"] if m["id"] == "local/CorpAI-Gen"), None)
            self.assertIsNotNone(local_model)
            self.assertEqual(local_model["id"], "local/CorpAI-Gen")
            self.assertEqual(local_model["name"], "local/CorpAI-Gen | Legal & Compliance")

    async def test_resolve_cloud_model_aliases_routing(self):
        """Verifica que peticiones con el alias descriptivo o ID limpio enruten correctamente a CorpAI-Gen."""
        token = "test-token"
        key_doc = {"services": ["gemma"], "allowed_providers": []}

        with patch.dict(os.environ, {"LLAMA_MODEL_ID": "CorpAI-Gen", "LLAMA_ALIAS": "CorpAI-Gen | Legal & Compliance"}):
            # 1. Petición con local/CorpAI-Gen
            is_cloud, actual, _, _, _ = await resolve_cloud_model("local/CorpAI-Gen", token, key_doc)
            self.assertFalse(is_cloud)
            self.assertEqual(actual, "CorpAI-Gen")

            # 2. Petición con local/CorpAI-Gen | Legal & Compliance
            is_cloud, actual, _, _, _ = await resolve_cloud_model("local/CorpAI-Gen | Legal & Compliance", token, key_doc)
            self.assertFalse(is_cloud)
            self.assertEqual(actual, "CorpAI-Gen")

            # 3. Petición directa con CorpAI-Gen | Legal & Compliance
            is_cloud, actual, _, _, _ = await resolve_cloud_model("CorpAI-Gen | Legal & Compliance", token, key_doc)
            self.assertFalse(is_cloud)
            self.assertEqual(actual, "CorpAI-Gen")


if __name__ == "__main__":
    unittest.main()
