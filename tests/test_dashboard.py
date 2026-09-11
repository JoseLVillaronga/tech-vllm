import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from dashboard.app import create_app
from dashboard.core import (
    slugify_provider_name,
    check_and_reset_key_quota_dict,
    parse_env_to_dict
)
import app_dashboard


class TestDashboardModular(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        # Establecer sesión autenticada como admin para pruebas funcionales
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "username": "admin",
                "role": "admin",
                "is_local": True
            }

    def test_app_dashboard_backward_compatibility(self):
        """Verifica que el entrypoint app_dashboard.py exponga la app y todas las funciones clave."""
        self.assertIsNotNone(app_dashboard.app)
        self.assertTrue(callable(app_dashboard.main))
        self.assertIsInstance(app_dashboard.PORT, int)
        self.assertTrue(callable(app_dashboard.get_db))
        self.assertTrue(callable(app_dashboard.slugify_provider_name))
        self.assertTrue(callable(app_dashboard.check_and_reset_key_quota_dict))

    def test_slugify_provider_name(self):
        """Prueba la normalización segura de nombres de proveedores."""
        self.assertEqual(slugify_provider_name("OpenAI"), "openai")
        self.assertEqual(slugify_provider_name("Together AI"), "together_ai")
        self.assertEqual(slugify_provider_name("  Groq!! "), "groq")
        self.assertEqual(slugify_provider_name(""), "cloud")

    def test_quota_reset_logic(self):
        """Prueba la lógica de reset de cuotas diarias y mensuales de claves API."""
        mock_db = MagicMock()
        yesterday = datetime.now(timezone.utc) - timedelta(days=2)
        
        # Caso 1: cuota 'none' no se reinicia
        key_none = {"_id": "k1", "quota_reset": "none", "used_tokens": 100, "last_reset_at": yesterday}
        res_none = check_and_reset_key_quota_dict(key_none, mock_db)
        self.assertEqual(res_none["used_tokens"], 100)
        mock_db.api_keys.update_one.assert_not_called()

        # Caso 2: cuota 'daily' de hace 2 días se reinicia a 0
        key_daily = {"_id": "k2", "quota_reset": "daily", "used_tokens": 500, "last_reset_at": yesterday}
        res_daily = check_and_reset_key_quota_dict(key_daily, mock_db)
        self.assertEqual(res_daily["used_tokens"], 0)
        mock_db.api_keys.update_one.assert_called_once()

    def test_frontend_index(self):
        """Verifica que la ruta raíz sirva el template HTML principal."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"vLLM", response.data)

    def test_frontend_favicon(self):
        """Verifica que la ruta de favicon responda correctamente."""
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 200)

    def test_api_status(self):
        """Verifica que el endpoint /api/status entregue métricas del sistema y servicios."""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("system", data)
        self.assertIn("services", data)
        self.assertIn("cpu", data["system"])
        self.assertIn("vram_percent", data["system"])

    def test_api_config(self):
        """Verifica que /api/config entregue la configuración parseada."""
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, dict)

    @patch("dashboard.routes.keys.get_db")
    def test_api_keys_list(self, mock_get_db):
        """Verifica la respuesta del endpoint /api/keys."""
        mock_db = MagicMock()
        mock_db.api_keys.find.return_value = [
            {"_id": "key1", "name": "Test Key", "quota_reset": "none", "used_tokens": 0}
        ]
        mock_db.api_key_models.find.return_value = []
        mock_get_db.return_value = mock_db

        response = self.client.get("/api/keys")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Test Key")

    @patch("dashboard.routes.security.get_db")
    def test_api_ip_rules_list(self, mock_get_db):
        """Verifica la lista de reglas IP."""
        mock_db = MagicMock()
        mock_db.ip_rules.find.return_value = [
            {"_id": "r1", "name": "Office", "network": "192.168.1.0/24", "action": "whitelist", "is_active": True}
        ]
        mock_get_db.return_value = mock_db

        response = self.client.get("/api/ip-rules")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["network"], "192.168.1.0/24")

    @patch("dashboard.routes.cloud.get_db")
    def test_api_cloud_providers_list(self, mock_get_db):
        """Verifica la lista de proveedores cloud con enmascaramiento de claves."""
        mock_db = MagicMock()
        mock_db.cloud_providers.find.return_value = [
            {"_id": "p1", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "api_key": "sk-1234567890abcdef", "is_active": True}
        ]
        mock_get_db.return_value = mock_db

        response = self.client.get("/api/cloud-providers")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["api_key"].endswith("..."))

    @patch("dashboard.routes.voices.get_db")
    def test_api_voices_list(self, mock_get_db):
        """Verifica la lista de perfiles de voz."""
        mock_db = MagicMock()
        mock_db.reference_voices.find.return_value = [
            {"_id": "v1", "name": "Carlos", "description": "Voz grave", "audio_path": "/static/audio/clones/carlos.wav", "is_active": True}
        ]
        mock_get_db.return_value = mock_db

        response = self.client.get("/api/voices")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Carlos")


    @patch("dashboard.routes.cloud.requests.get")
    @patch("dashboard.routes.cloud.get_db")
    def test_api_cloud_provider_models_caching(self, mock_get_db, mock_requests_get):
        """Verifica que el endpoint de modelos de proveedor use la caché en memoria y no repita peticiones externas."""
        from bson import ObjectId
        mock_db = MagicMock()
        mock_db.cloud_providers.find_one.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "sk-or-test"
        }
        mock_get_db.return_value = mock_db

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "meta-llama/llama-3-8b"}]}
        mock_requests_get.return_value = mock_resp

        # Primera llamada: hace la petición externa
        res1 = self.client.get("/api/cloud-providers/507f1f77bcf86cd799439011/models?refresh=true")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(mock_requests_get.call_count, 1)

        # Segunda llamada: responde desde la caché en memoria sin invocar requests.get
        res2 = self.client.get("/api/cloud-providers/507f1f77bcf86cd799439011/models")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(mock_requests_get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
