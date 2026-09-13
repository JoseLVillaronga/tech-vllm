"""
tests/test_dashboard_auth.py - Suite de pruebas de seguridad y autenticación para el Dashboard.
"""

import unittest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash
from dashboard.app import create_app
from dashboard.core.auth_service import (
    is_localhost_ip,
    resolve_client_ip_dashboard,
    create_dashboard_user,
    update_dashboard_user,
    reset_dashboard_user_password,
    delete_dashboard_user
)


class TestDashboardAuth(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_localhost_ip_detection(self):
        """Verifica la detección matemática de direcciones loopback (localhost)."""
        self.assertTrue(is_localhost_ip("127.0.0.1"))
        self.assertTrue(is_localhost_ip("127.0.1.1"))
        self.assertTrue(is_localhost_ip("127.0.0.254"))
        self.assertTrue(is_localhost_ip("::1"))

        self.assertFalse(is_localhost_ip("192.168.1.100"))
        self.assertFalse(is_localhost_ip("10.0.0.1"))
        self.assertFalse(is_localhost_ip("172.16.0.5"))
        self.assertFalse(is_localhost_ip("203.0.113.195"))
        self.assertFalse(is_localhost_ip(""))
        self.assertFalse(is_localhost_ip("invalid-ip"))

    def test_resolve_client_ip_dashboard_anti_spoofing(self):
        """Verifica que clientes externos directos no puedan suplantar IP mediante cabeceras."""
        # 1. Petición directa externa (remote_addr = 192.168.1.50)
        req_mock = MagicMock()
        req_mock.remote_addr = "192.168.1.50"
        req_mock.headers = {"X-Forwarded-For": "127.0.0.1"}

        # Las cabeceras deben ser ignoradas porque el socket no es de confianza
        resolved = resolve_client_ip_dashboard(req_mock)
        self.assertEqual(resolved, "192.168.1.50")

        # 2. Petición a través de proxy local de confianza (127.0.0.1)
        req_proxy = MagicMock()
        req_proxy.remote_addr = "127.0.0.1"
        req_proxy.headers = {"X-Forwarded-For": "190.220.1.25, 127.0.0.1"}

        # Debe descartar 127.0.0.1 y retornar la IP cliente real 190.220.1.25
        resolved_proxy = resolve_client_ip_dashboard(req_proxy)
        self.assertEqual(resolved_proxy, "190.220.1.25")

    @patch.dict("os.environ", {"ADMIN_PASS": "clave_super_secreta_123"})
    @patch("dashboard.core.auth_service.ADMIN_PASS", "clave_super_secreta_123")
    def test_admin_login_localhost_success(self):
        """Verifica que el usuario admin pueda loguearse con ADMIN_PASS desde localhost."""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "clave_super_secreta_123"},
            environ_overrides={"REMOTE_ADDR": "127.0.0.1"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["username"], "admin")
        self.assertEqual(data["user"]["role"], "admin")
        self.assertTrue(data["user"]["is_local"])

    @patch.dict("os.environ", {"ADMIN_PASS": "clave_super_secreta_123"})
    @patch("dashboard.core.auth_service.ADMIN_PASS", "clave_super_secreta_123")
    def test_admin_login_localhost_wrong_pass(self):
        """Verifica que falle el login de admin con contraseña incorrecta."""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "clave_erronea"},
            environ_overrides={"REMOTE_ADDR": "127.0.0.1"}
        )
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertIn("error", data)

    @patch.dict("os.environ", {"ADMIN_PASS": "clave_super_secreta_123"})
    @patch("dashboard.core.auth_service.ADMIN_PASS", "clave_super_secreta_123")
    def test_admin_login_remote_ip_strictly_forbidden(self):
        """Regla crítica: El usuario admin NO puede loguearse desde IP remota bajo ninguna circunstancia."""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "clave_super_secreta_123"},
            environ_overrides={"REMOTE_ADDR": "192.168.1.88"}
        )
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertIn("solo puede iniciar sesión desde localhost", data.get("error", ""))

    @patch.dict("os.environ", {"ADMIN_PASS": "clave_super_secreta_123"})
    @patch("dashboard.core.auth_service.ADMIN_PASS", "clave_super_secreta_123")
    def test_admin_login_remote_spoofed_headers_forbidden(self):
        """Verifica que un cliente remoto no eluda la restricción enviando X-Forwarded-For falso."""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "clave_super_secreta_123"},
            headers={"X-Forwarded-For": "127.0.0.1"},
            environ_overrides={"REMOTE_ADDR": "192.168.1.88"}
        )
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertIn("solo puede iniciar sesión desde localhost", data.get("error", ""))

    @patch("dashboard.core.auth_service.get_db")
    def test_remote_user_login_success(self, mock_get_db):
        """Verifica que un usuario remoto pueda loguearse desde una IP remota."""
        mock_db = MagicMock()
        mock_db.dashboard_users.find_one.return_value = {
            "_id": "u1",
            "username": "operador1",
            "password_hash": generate_password_hash("clave_remota_456"),
            "role": "operator",
            "is_active": True
        }
        mock_get_db.return_value = mock_db

        response = self.client.post(
            "/api/auth/login",
            json={"username": "operador1", "password": "clave_remota_456"},
            environ_overrides={"REMOTE_ADDR": "192.168.1.88"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data["user"]["username"], "operador1")
        self.assertEqual(data["user"]["role"], "operator")
        self.assertFalse(data["user"]["is_local"])

    @patch("dashboard.core.auth_service.get_db")
    def test_remote_user_suspended_login_rejected(self, mock_get_db):
        """Verifica que un usuario remoto desactivado sea rechazado."""
        mock_db = MagicMock()
        mock_db.dashboard_users.find_one.return_value = {
            "_id": "u2",
            "username": "usuario_suspendido",
            "password_hash": generate_password_hash("clave_123456"),
            "role": "operator",
            "is_active": False
        }
        mock_get_db.return_value = mock_db

        response = self.client.post(
            "/api/auth/login",
            json={"username": "usuario_suspendido", "password": "clave_123456"},
            environ_overrides={"REMOTE_ADDR": "192.168.1.88"}
        )
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertIn("desactivada o suspendida", data.get("error", ""))

    @patch("dashboard.core.auth_service.get_db")
    def test_create_user_admin_name_reserved(self, mock_get_db):
        """Verifica que no se permita registrar un usuario con el nombre reservado 'admin'."""
        success, msg = create_dashboard_user("admin", "clave123456")
        self.assertFalse(success)
        self.assertIn("reservado exclusivamente", msg)

    @patch("dashboard.core.auth_service.get_db")
    def test_create_user_success(self, mock_get_db):
        """Verifica la inserción correcta de un usuario remoto en MongoDB."""
        mock_db = MagicMock()
        mock_db.dashboard_users.find_one.return_value = None
        mock_get_db.return_value = mock_db

        success, msg = create_dashboard_user("operador_nuevo", "password_seguro_123", role="operator")
        self.assertTrue(success)
        mock_db.dashboard_users.insert_one.assert_called_once()
        args, kwargs = mock_db.dashboard_users.insert_one.call_args
        inserted_doc = args[0]
        self.assertEqual(inserted_doc["username"], "operador_nuevo")
        self.assertEqual(inserted_doc["role"], "operator")
        self.assertTrue(inserted_doc["password_hash"].startswith("scrypt:") or inserted_doc["password_hash"].startswith("pbkdf2:"))

    def test_unauthenticated_redirection_and_protection(self):
        """Verifica que el middleware before_request proteja las rutas no autenticadas."""
        # Ruta web / sin sesión redirige a /login
        resp_web = self.client.get("/")
        self.assertEqual(resp_web.status_code, 302)
        self.assertIn("/login", resp_web.headers["Location"])

        # Endpoint API sin sesión devuelve 401 JSON
        resp_api = self.client.get("/api/status")
        self.assertEqual(resp_api.status_code, 401)
        self.assertIn("No autenticado", resp_api.get_json().get("error", ""))

        # Ruta /login es accesible sin autenticación previa
        resp_login = self.client.get("/login")
        self.assertEqual(resp_login.status_code, 200)

        # Ruta de favicon es accesible
        resp_fav = self.client.get("/favicon.ico")
        self.assertEqual(resp_fav.status_code, 200)

    def test_users_api_requires_admin(self):
        """Verifica que endpoints /api/users requieran rol admin."""
        # Con sesión de rol operator:
        with self.client.session_transaction() as sess:
            sess["user"] = {"username": "operador1", "role": "operator", "is_local": False}

        resp_forbidden = self.client.get("/api/users")
        self.assertEqual(resp_forbidden.status_code, 403)

        # Con sesión de rol admin:
        with self.client.session_transaction() as sess:
            sess["user"] = {"username": "admin", "role": "admin", "is_local": True}

        with patch("dashboard.routes.users.list_dashboard_users", return_value=[]):
            resp_allowed = self.client.get("/api/users")
            self.assertEqual(resp_allowed.status_code, 200)

    @patch("dashboard.core.auth_service.get_db")
    def test_create_user_allowed_rag_tables(self, mock_get_db):
        """Verifica la asignación y validación de bases RAG permitidas."""
        mock_db = MagicMock()
        mock_db.dashboard_users.find_one.return_value = None
        mock_get_db.return_value = mock_db

        # 1. Operador con tabla por defecto
        success, _ = create_dashboard_user("op_default", "pass123456", role="operator")
        self.assertTrue(success)
        doc1 = mock_db.dashboard_users.insert_one.call_args[0][0]
        self.assertEqual(doc1["allowed_rag_tables"], ["teccam_knowledge_base"])

        # 2. Operador con tablas personalizadas
        success, _ = create_dashboard_user("op_custom", "pass123456", role="operator", allowed_rag_tables=["kb_empresa_a", "kb_empresa_b"])
        self.assertTrue(success)
        doc2 = mock_db.dashboard_users.insert_one.call_args[0][0]
        self.assertEqual(doc2["allowed_rag_tables"], ["kb_empresa_a", "kb_empresa_b"])

        # 3. Operador sin ninguna tabla debe fallar
        success, err = create_dashboard_user("op_empty", "pass123456", role="operator", allowed_rag_tables=[])
        self.assertFalse(success)
        self.assertIn("al menos una base RAG permitida", err)

        # 4. Admin siempre recibe acceso total ["*"]
        success, _ = create_dashboard_user("admin_remoto", "pass123456", role="admin", allowed_rag_tables=["kb_algo"])
        self.assertTrue(success)
        doc4 = mock_db.dashboard_users.insert_one.call_args[0][0]
        self.assertEqual(doc4["allowed_rag_tables"], ["*"])

    @patch("dashboard.core.auth_service.get_db")
    def test_update_user_allowed_rag_tables(self, mock_get_db):
        """Verifica la actualización de bases RAG y rol en usuarios existentes."""
        mock_db = MagicMock()
        mock_db.dashboard_users.find_one.return_value = {
            "username": "op_test",
            "role": "operator",
            "allowed_rag_tables": ["teccam_knowledge_base"],
            "is_active": True
        }
        mock_get_db.return_value = mock_db

        # Actualizar bases RAG
        success, _ = update_dashboard_user("op_test", allowed_rag_tables=["kb_nueva"])
        self.assertTrue(success)
        update_set = mock_db.dashboard_users.update_one.call_args[0][1]["$set"]
        self.assertEqual(update_set["allowed_rag_tables"], ["kb_nueva"])

        # Si se promueve a admin, recibe ["*"]
        success, _ = update_dashboard_user("op_test", role="admin")
        self.assertTrue(success)
        update_set2 = mock_db.dashboard_users.update_one.call_args[0][1]["$set"]
        self.assertEqual(update_set2["allowed_rag_tables"], ["*"])

    def test_operator_tab_rag_restrictions(self):
        """Verifica el filtrado multi-tenant de bases RAG y restricción de búsqueda para operadores."""
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "username": "op_tenant",
                "role": "operator",
                "allowed_rag_tables": ["kb_mi_empresa"],
                "is_local": False
            }

        # 1. /api/rag/bases solo debe listar las bases permitidas al operador
        mock_bases = [
            {"table_name": "teccam_knowledge_base", "display_name": "Teccam"},
            {"table_name": "kb_mi_empresa", "display_name": "Mi Empresa"},
            {"table_name": "kb_otra_empresa", "display_name": "Otra Empresa"}
        ]
        with patch("rag_engine.list_knowledge_bases", return_value=mock_bases):
            resp = self.client.get("/api/rag/bases")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            returned_tables = [b["table_name"] for b in data["bases"]]
            self.assertEqual(returned_tables, ["kb_mi_empresa"])

        # 2. Búsqueda RAG en una base no permitida debe dar 403 Forbidden
        resp_denied = self.client.post("/api/rag/search", json={
            "query": "consulta confidencial",
            "table_name": "kb_otra_empresa"
        })
        self.assertEqual(resp_denied.status_code, 403)
        self.assertIn("No tiene permisos asignados", resp_denied.get_json().get("error", ""))

        # 3. Acciones administrativas de RAG bloqueadas para operador
        self.assertEqual(self.client.post("/api/rag/bases", json={"empresa": "Nueva"}).status_code, 403)
        self.assertEqual(self.client.post("/api/rag/sync", json={}).status_code, 403)
        self.assertEqual(self.client.post("/api/rag/sync-metadata", json={}).status_code, 403)
        self.assertEqual(self.client.delete("/api/rag/bases/kb_mi_empresa").status_code, 403)

    def test_operator_blocked_from_admin_tabs_and_controls(self):
        """Verifica que el operador tenga bloqueados el control de servicios, .env, keys, seguridad y alineación."""
        with self.client.session_transaction() as sess:
            sess["user"] = {
                "username": "operador_prueba",
                "role": "operator",
                "allowed_rag_tables": ["teccam_knowledge_base"],
                "is_local": False
            }

        # Control de servicios (Start, Stop, Restart)
        self.assertEqual(self.client.post("/api/service/llm/restart").status_code, 403)
        self.assertEqual(self.client.post("/api/service/tts/stop").status_code, 403)

        # Variables .env
        self.assertEqual(self.client.get("/api/config").status_code, 403)
        self.assertEqual(self.client.post("/api/config", json={}).status_code, 403)

        # Seguridad y Claves API
        self.assertEqual(self.client.get("/api/keys").status_code, 403)
        self.assertEqual(self.client.get("/api/ip-rules").status_code, 403)
        self.assertEqual(self.client.get("/api/cloud-providers").status_code, 403)

        # Alineación MEA
        self.assertEqual(self.client.get("/api/alignment/settings").status_code, 403)
        self.assertEqual(self.client.post("/api/alignment/settings", json={}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
