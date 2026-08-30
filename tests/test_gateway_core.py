import unittest
import ipaddress
from unittest.mock import MagicMock
from gateway.core.ip_resolver import resolve_client_ip, TRUSTED_PROXIES
from gateway.core.ip_rules import is_ip_allowed
from gateway.core.auth import extract_token, validate_token_doc


class TestGatewayCore(unittest.TestCase):

    def test_trusted_proxies_configured(self):
        self.assertGreater(len(TRUSTED_PROXIES), 0)
        self.assertTrue(any(ipaddress.ip_address("127.0.0.1") in net for net in TRUSTED_PROXIES))

    def test_resolve_client_ip_direct(self):
        request = MagicMock()
        request.client.host = "200.61.48.132"
        request.headers = {"x-forwarded-for": "10.0.0.1"}
        # Direct untrusted connection ignores spoofed x-forwarded-for header
        ip = resolve_client_ip(request)
        self.assertEqual(ip, "200.61.48.132")

    def test_resolve_client_ip_via_trusted_proxy(self):
        request = MagicMock()
        request.client.host = "127.0.0.1"  # Trusted Caddy proxy
        request.headers = {"x-forwarded-for": "200.61.48.132, 127.0.0.1"}
        # Resolves the leftmost untrusted IP
        ip = resolve_client_ip(request)
        self.assertEqual(ip, "200.61.48.132")

    def test_extract_token_bearer(self):
        request = MagicMock()
        request.headers = {"authorization": "Bearer my-secret-token"}
        request.query_params = {}
        self.assertEqual(extract_token(request), "my-secret-token")

    def test_extract_token_x_api_key(self):
        request = MagicMock()
        request.headers = {"x-api-key": "my-openwebui-key"}
        request.query_params = {}
        self.assertEqual(extract_token(request), "my-openwebui-key")

    def test_extract_token_query_param(self):
        request = MagicMock()
        request.headers = {}
        request.query_params = {"api_key": "my-query-key"}
        self.assertEqual(extract_token(request), "my-query-key")

    def test_validate_token_doc_master(self):
        master_doc = {"name": "Master Key"}
        self.assertTrue(validate_token_doc(master_doc, "gemma"))
        self.assertTrue(validate_token_doc(master_doc, "docling"))

    def test_validate_token_doc_rbac(self):
        doc = {
            "name": "Test Key",
            "services": ["gemma", "docling"],
            "allowed_providers": []
        }
        self.assertTrue(validate_token_doc(doc, "gemma"))
        self.assertTrue(validate_token_doc(doc, "docling"))
        self.assertFalse(validate_token_doc(doc, "whisper"))


if __name__ == "__main__":
    unittest.main()
