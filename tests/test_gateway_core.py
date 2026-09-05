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

    def test_get_key_doc_master_key_restricted_by_default(self):
        import os
        from gateway.core.auth import get_key_doc, MASTER_KEY
        os.environ["ALLOW_MASTER_KEY_ON_GATEWAY"] = "false"
        self.assertIsNone(get_key_doc(MASTER_KEY))

    def test_get_key_doc_master_key_allowed_when_enabled(self):
        import os
        from gateway.core.auth import get_key_doc, MASTER_KEY
        os.environ["ALLOW_MASTER_KEY_ON_GATEWAY"] = "true"
        doc = get_key_doc(MASTER_KEY)
        self.assertIsNotNone(doc)
        self.assertEqual(doc.get("name"), "Master Key")
        os.environ["ALLOW_MASTER_KEY_ON_GATEWAY"] = "false"


    def test_fail2ban_config_defaults_and_env(self):
        import os
        from gateway.core.fail2ban import get_fail2ban_config

        # Con variables por defecto
        os.environ.pop("FAIL2BAN_MAX_FAILURES", None)
        os.environ.pop("FAIL2BAN_WINDOW_SECONDS", None)
        os.environ.pop("FAIL2BAN_BAN_HOURS", None)
        max_f, win_s, ban_h = get_fail2ban_config()
        self.assertEqual(max_f, 3)
        self.assertEqual(win_s, 300)
        self.assertEqual(ban_h, 48)

        # Con variables personalizadas
        os.environ["FAIL2BAN_MAX_FAILURES"] = "5"
        os.environ["FAIL2BAN_WINDOW_SECONDS"] = "60"
        os.environ["FAIL2BAN_BAN_HOURS"] = "12"
        max_f, win_s, ban_h = get_fail2ban_config()
        self.assertEqual(max_f, 5)
        self.assertEqual(win_s, 60)
        self.assertEqual(ban_h, 12)

    def test_check_ip_access_and_silent_drop(self):
        import os
        import gateway.core.ip_rules as ip_rules

        # Configurar blacklist en memoria
        ip_rules.cached_blacklist = [ipaddress.ip_network("198.51.100.0/24")]
        ip_rules.cached_whitelist = []
        ip_rules.clear_blacklist_notice_counts()
        os.environ["BLACKLIST_MAX_NOTICES"] = "3"

        allowed_ip = ipaddress.ip_address("192.168.1.100")
        banned_ip = ipaddress.ip_address("198.51.100.42")

        # IP Permitida
        allowed, reason, silent_drop = ip_rules.check_ip_access(allowed_ip)
        self.assertTrue(allowed)
        self.assertFalse(silent_drop)

        # Intentos 1 a 3 para IP en lista negra (emite 403 formal)
        for i in range(1, 4):
            allowed, reason, silent_drop = ip_rules.check_ip_access(banned_ip)
            self.assertFalse(allowed)
            self.assertFalse(silent_drop, f"El intento {i} no debería ser silent drop aún")
            self.assertEqual(ip_rules.get_blacklist_notice_count(str(banned_ip)), i)

        # Intento 4 en adelante: silent_drop debe ser True
        allowed, reason, silent_drop = ip_rules.check_ip_access(banned_ip)
        self.assertFalse(allowed)
        self.assertTrue(silent_drop, "El intento 4 debe activar silent drop")

        # Verificar compatibilidad hacia atrás de is_ip_allowed
        allowed_legacy, reason_legacy = ip_rules.is_ip_allowed(banned_ip)
        self.assertFalse(allowed_legacy)
        self.assertIn("Lista Negra", reason_legacy)

        # Limpiar
        ip_rules.cached_blacklist = []
        ip_rules.clear_blacklist_notice_counts()

    def test_gateway_proxy_silent_drop_e2e(self):
        import os
        from fastapi.testclient import TestClient
        import gateway.core.ip_rules as ip_rules
        from gateway.proxy.proxy_factory import create_proxy_app

        app = create_proxy_app(service_name="test_srv", target_port=19999, include_alignment=False)
        client = TestClient(app, client=("198.51.100.99", 50000))

        # Configurar IP 198.51.100.99 en blacklist
        ip_rules.cached_blacklist = [ipaddress.ip_network("198.51.100.99/32")]
        ip_rules.cached_whitelist = []
        ip_rules.clear_blacklist_notice_counts()
        os.environ["BLACKLIST_MAX_NOTICES"] = "3"

        # Primeros 3 intentos: HTTP 403 con JSON detallado
        for i in range(1, 4):
            response = client.get("/v1/models")
            self.assertEqual(response.status_code, 403)
            self.assertIn("Acceso denegado: IP Bloqueada en Lista Negra.", response.text)

        # Intento 4: Silent Drop -> HTTP 403 con cuerpo vacío (0 bytes) y Connection: close
        response_silent = client.get("/v1/models")
        self.assertEqual(response_silent.status_code, 403)
        self.assertEqual(response_silent.content, b"")
        self.assertEqual(response_silent.headers.get("connection"), "close")

        # Limpieza
        ip_rules.cached_blacklist = []
        ip_rules.clear_blacklist_notice_counts()

    def test_gateway_proxy_master_key_triggers_fail2ban(self):
        import os
        from fastapi.testclient import TestClient
        from gateway.proxy.proxy_factory import create_proxy_app
        from gateway.core.auth import MASTER_KEY
        import gateway.core.fail2ban as f2b

        os.environ["ALLOW_MASTER_KEY_ON_GATEWAY"] = "false"
        client_ip = "192.0.2.77"
        f2b.failed_attempts.pop(client_ip, None)

        app = create_proxy_app(service_name="test_srv", target_port=19999, include_alignment=False)
        client = TestClient(app, client=(client_ip, 50000))

        response = client.get("/v1/models", headers={"Authorization": f"Bearer {MASTER_KEY}"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("La Clave Maestra está reservada exclusivamente", response.text)

        # Verificar que la IP quedó registrada en el historial de fallos de fail2ban
        self.assertIn(client_ip, f2b.failed_attempts)
        self.assertEqual(len(f2b.failed_attempts[client_ip]), 1)

        # Limpiar
        f2b.failed_attempts.pop(client_ip, None)

    def test_fail2ban_loopback_exclusion(self):
        import os
        import asyncio
        import gateway.core.fail2ban as f2b

        # 1. Por defecto o con FAIL2BAN_EXCLUDE_LOOPBACK="true", loopback no se registra
        os.environ["FAIL2BAN_EXCLUDE_LOOPBACK"] = "true"
        self.assertTrue(f2b.should_exclude_loopback())

        loopback_ip = "127.0.0.1"
        f2b.failed_attempts.pop(loopback_ip, None)

        asyncio.run(f2b.register_failed_attempt(loopback_ip))
        self.assertNotIn(loopback_ip, f2b.failed_attempts)

        # 2. Con FAIL2BAN_EXCLUDE_LOOPBACK="false" (modo estricto), loopback sí se registra
        os.environ["FAIL2BAN_EXCLUDE_LOOPBACK"] = "false"
        self.assertFalse(f2b.should_exclude_loopback())

        asyncio.run(f2b.register_failed_attempt(loopback_ip))
        self.assertIn(loopback_ip, f2b.failed_attempts)
        self.assertEqual(len(f2b.failed_attempts[loopback_ip]), 1)

        # Limpiar
        f2b.failed_attempts.pop(loopback_ip, None)
        os.environ["FAIL2BAN_EXCLUDE_LOOPBACK"] = "true"


if __name__ == "__main__":
    unittest.main()
