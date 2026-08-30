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


if __name__ == "__main__":
    unittest.main()
