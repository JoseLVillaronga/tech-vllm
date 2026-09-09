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

    def test_enrich_chat_payload_grounding_anti_decay(self):
        import asyncio
        from gateway.core.alignment_engine import enrich_chat_payload

        tools_with_rag = [
            {"type": "function", "function": {"name": "buscar_en_base_de_conocimiento"}}
        ]

        # 1. Consulta sensible (Constitución / Mecanismo) con herramientas RAG -> Debe inyectar recordatorio
        data_sensible = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "¿Cuál es el mecanismo establecido en la Constitución Nacional para reformar la Carta Magna?"}
            ],
            "tools": tools_with_rag
        }
        res = asyncio.run(enrich_chat_payload(data_sensible, actual_model="gemma", is_cloud_request=False))
        last_msg = res["messages"][-1]
        self.assertIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]", last_msg["content"])
        self.assertIn("procedimientos, contratos, políticas", last_msg["content"])

        # 2. Consulta de procedimiento interno -> Debe inyectar recordatorio
        data_proc = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "¿Cuáles son los pasos del procedimiento de compras y el contrato de servicio?"}
            ],
            "tools": tools_with_rag
        }
        res_proc = asyncio.run(enrich_chat_payload(data_proc, actual_model="gemma", is_cloud_request=False))
        self.assertIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]", res_proc["messages"][-1]["content"])

        # 3. Consulta general/conversacional -> NO debe inyectar recordatorio
        data_chat = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hola, buenos días, ¿cómo estás hoy?"}
            ],
            "tools": tools_with_rag
        }
        res_chat = asyncio.run(enrich_chat_payload(data_chat, actual_model="gemma", is_cloud_request=False))
        self.assertNotIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]", res_chat["messages"][-1]["content"])

        # 4. Sin herramientas RAG disponibles -> NO debe inyectar recordatorio
        data_no_tools = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "¿Cuál es el mecanismo de la Constitución?"}
            ],
            "tools": []
        }
        res_no_tools = asyncio.run(enrich_chat_payload(data_no_tools, actual_model="gemma", is_cloud_request=False))
        self.assertNotIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]", res_no_tools["messages"][-1]["content"])

        # 5. Consulta institucional / órganos (Defensor del Pueblo / Función) -> Debe inyectar recordatorio
        data_institucional = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "¿Cuál es la función del Defensor del Pueblo en el ordenamiento jurídico argentino?"}
            ],
            "tools": tools_with_rag
        }
        res_inst = asyncio.run(enrich_chat_payload(data_institucional, actual_model="gemma", is_cloud_request=False))
        self.assertIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (MEA)]", res_inst["messages"][-1]["content"])

        # 6. Repregunta de seguimiento ("Dame mas detalles") tras consulta previa con grounding -> Debe inyectar recordatorio de seguimiento
        data_followup = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "¿Qué delitos se regulan en el Título I del Libro II del Código Penal argentino?"},
                {"role": "assistant", "content": "El Título I regula los Delitos contra las Personas (doc_id: 6a9e2d4236300fe5f0afb9d8)."},
                {"role": "user", "content": "Dame mas detalles"}
            ],
            "tools": tools_with_rag
        }
        res_followup = asyncio.run(enrich_chat_payload(data_followup, actual_model="gemma", is_cloud_request=False))
        last_followup_msg = res_followup["messages"][-1]["content"]
        self.assertIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (SEGUIMIENTO - MEA)]", last_followup_msg)
        self.assertIn("obtener_estructura_documento", last_followup_msg)

        # 7. Repregunta de seguimiento ("amplía") tras asistente con tool_calls -> Debe inyectar recordatorio de seguimiento
        data_followup_tools = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Consulta general"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "buscar_en_base_de_conocimiento"}}]},
                {"role": "tool", "content": "Resultados de la norma"},
                {"role": "assistant", "content": "Aquí tienes la introducción."},
                {"role": "user", "content": "amplía"}
            ],
            "tools": tools_with_rag
        }
        res_ft = asyncio.run(enrich_chat_payload(data_followup_tools, actual_model="gemma", is_cloud_request=False))
        self.assertIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO (SEGUIMIENTO - MEA)]", res_ft["messages"][-1]["content"])

        # 8. Consulta corta en chat puramente informal sin grounding previo -> NO debe inyectar
        data_informal_followup = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hola amigo"},
                {"role": "assistant", "content": "Hola! En qué te puedo ayudar hoy?"},
                {"role": "user", "content": "dame un chiste"}
            ],
            "tools": tools_with_rag
        }
        res_inf = asyncio.run(enrich_chat_payload(data_informal_followup, actual_model="gemma", is_cloud_request=False))
        self.assertNotIn("[DIRECTIVA DE CONTROL Y GROUNDING OBLIGATORIO", res_inf["messages"][-1]["content"])

        # 9. Conversación con más de 6 turnos de usuario -> Debe podar a los últimos 6 turnos conservando el system prompt y anclando el último turno
        long_chat_msgs = [{"role": "system", "content": "You are a helpful assistant."}]
        for i in range(1, 23):  # 22 turnos
            long_chat_msgs.append({"role": "user", "content": f"Turno {i}"})
            long_chat_msgs.append({"role": "assistant", "content": f"Respuesta {i}"})

        data_long = {"messages": long_chat_msgs, "tools": []}
        res_pruned = asyncio.run(enrich_chat_payload(data_long, actual_model="gemma", is_cloud_request=False))
        user_msgs_in_res = [m for m in res_pruned["messages"] if m.get("role") == "user"]
        self.assertEqual(len(user_msgs_in_res), 6)
        self.assertEqual(user_msgs_in_res[0]["content"], "Turno 17")
        self.assertIn("Turno 22", user_msgs_in_res[-1]["content"])
        self.assertTrue(user_msgs_in_res[-1]["content"].startswith("[CONSULTA ACTUAL DEL USUARIO]:"))
        self.assertEqual(res_pruned["messages"][0]["role"], "system")
        self.assertFalse(res_pruned.get("cache_prompt"))

        # 10. Turno en medio de un bucle de herramientas (último mensaje role == 'tool')
        # Debe inyectar el pie de foco activo con la consulta limpia del usuario
        data_tool_loop = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "¿Qué reformas introdujo la Ley 27.742 laboral?"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "buscar"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": "Fragmentos con mención accidental al Decreto 70/2023."}
            ],
            "tools": [{"type": "function", "function": {"name": "buscar"}}]
        }
        res_tool = asyncio.run(enrich_chat_payload(data_tool_loop, actual_model="gemma", is_cloud_request=False))
        last_tool = res_tool["messages"][-1]
        self.assertEqual(last_tool["role"], "tool")
        self.assertIn("[RECORDATORIO DE FOCO ACTIVO Y REGLA DE PERTINENCIA (ANTI-CROSSTALK)]", last_tool["content"])
        self.assertIn("¿Qué reformas introdujo la Ley 27.742 laboral?", last_tool["content"])
        self.assertIn("ESTRICTAMENTE PROHIBIDO desviar tu respuesta o tus próximas herramientas hacia temas de turnos anteriores", last_tool["content"])

        # 11. Modo Agentic (Puerto 8010 para Deepseek Harness / Benchmarks):
        # - System prompt virgen (sin invariantes MEA)
        # - Mensaje de usuario virgen (sin prefijo [CONSULTA ACTUAL DEL USUARIO])
        # - Foco activo inyectado en herramientas (en inglés para tareas en inglés)
        from gateway.core.alignment_engine import is_english_query
        self.assertTrue(is_english_query("Fix the KeyError in session_manager.py line 42"))
        self.assertTrue(is_english_query("Implement binary search in C++ and test it"))
        self.assertFalse(is_english_query("¿Qué reformas introdujo la Ley 27.742 laboral?"))
        self.assertFalse(is_english_query("Analizar el artículo 15 de la Constitución Nacional"))

        data_agentic_en = {
            "messages": [
                {"role": "system", "content": "You are an autonomous coding agent."},
                {"role": "user", "content": "Fix the NullPointerException in AuthController.java"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "run_bash"}}]},
                {"role": "tool", "tool_call_id": "t1", "content": "Compilation error logs and warnings."}
            ],
            "tools": [{"type": "function", "function": {"name": "run_bash"}}]
        }
        res_agentic = asyncio.run(enrich_chat_payload(data_agentic_en, actual_model="gemma", is_cloud_request=False, alignment_mode="agentic"))
        
        # System prompt no debe tener invariantes MEA
        sys_msg = res_agentic["messages"][0]["content"]
        self.assertNotIn("[DIRECTIVAS FUNDAMENTALES (MEA)]", sys_msg)
        self.assertNotIn("Principio de No-Daño", sys_msg)
        
        # User prompt no debe tener tags impuestos
        user_msg = res_agentic["messages"][1]["content"]
        self.assertEqual(user_msg, "Fix the NullPointerException in AuthController.java")
        self.assertNotIn("[CONSULTA ACTUAL DEL USUARIO]:", user_msg)
        
        # Tool output debe tener el recordatorio en inglés
        tool_out = res_agentic["messages"][-1]["content"]
        self.assertIn("[ACTIVE TASK FOCUS & RELEVANCE REMINDER (ANTI-CROSSTALK)]", tool_out)
        self.assertIn("Fix the NullPointerException in AuthController.java", tool_out)
        self.assertIn("You are executing tools to solve EXCLUSIVELY the current user task", tool_out)

    def test_format_company_profile_block(self):
        from gateway.core.alignment_engine import format_company_profile_block

        # 1. Perfil nulo o deshabilitado
        self.assertEqual(format_company_profile_block(None), "")
        self.assertEqual(format_company_profile_block({}), "")
        self.assertEqual(format_company_profile_block({"enabled": False, "company_name": "Test"}), "")

        # 2. Perfil habilitado completo
        full_profile = {
            "enabled": True,
            "company_name": "Logística y Transporte S.A.",
            "activity": "Transporte de Cargas Internacionales",
            "contact_info": "operaciones@logistica.com | +54 11 5555-4321",
            "business_hours": "Lunes a Viernes de 8 a 18 hs",
            "address": "Puerto Madero, Buenos Aires",
            "custom_instructions": "Tratar al cliente de Usted y solicitar CUIT para cotizaciones."
        }
        block = format_company_profile_block(full_profile)
        self.assertIn("[PERFIL E IDENTIDAD CORPORATIVA DE LA ORGANIZACIÓN]:", block)
        self.assertIn("Empresa / Razón Social: Logística y Transporte S.A.", block)
        self.assertIn("Actividad Principal: Transporte de Cargas Internacionales", block)
        self.assertIn("Canales de Contacto: operaciones@logistica.com | +54 11 5555-4321", block)
        self.assertIn("Horario de Atención: Lunes a Viernes de 8 a 18 hs", block)
        self.assertIn("Dirección / Ubicación: Puerto Madero, Buenos Aires", block)
        self.assertIn("Directrices Corporativas Específicas: Tratar al cliente de Usted y solicitar CUIT para cotizaciones.", block)
        self.assertIn("Directiva de Identidad Institucional:", block)

        # 3. Perfil habilitado parcial
        partial_profile = {
            "enabled": True,
            "company_name": "Consultora Alfa",
            "contact_info": "alfa@consultora.com"
        }
        p_block = format_company_profile_block(partial_profile)
        self.assertIn("Empresa / Razón Social: Consultora Alfa", p_block)
        self.assertIn("Canales de Contacto: alfa@consultora.com", p_block)
        self.assertNotIn("Actividad Principal:", p_block)
        self.assertNotIn("Horario de Atención:", p_block)

    def test_enrich_chat_payload_with_company_profile(self):
        import asyncio
        from gateway.core.alignment_engine import enrich_chat_payload

        corp_profile = {
            "enabled": True,
            "company_name": "Acme Distribuidora",
            "activity": "Insumos Eléctricos",
            "contact_info": "ventas@acme.com",
            "business_hours": "9 a 17 hs"
        }

        # Petición básica
        data = {
            "messages": [
                {"role": "user", "content": "Hola, ¿cuál es su horario de atención?"}
            ]
        }

        res = asyncio.run(enrich_chat_payload(
            data,
            actual_model="gemma",
            is_cloud_request=False,
            company_profile=corp_profile
        ))

        # Debe haberse inyectado el system prompt con el perfil corporativo
        sys_msg = next((m for m in res["messages"] if m.get("role") == "system"), None)
        self.assertIsNotNone(sys_msg)
        self.assertIn("[PERFIL E IDENTIDAD CORPORATIVA DE LA ORGANIZACIÓN]:", sys_msg["content"])
        self.assertIn("Acme Distribuidora", sys_msg["content"])
        self.assertIn("Insumos Eléctricos", sys_msg["content"])
        self.assertIn("ventas@acme.com", sys_msg["content"])

        # No duplicación en re-inyecciones
        res_dup = asyncio.run(enrich_chat_payload(
            res,
            actual_model="gemma",
            is_cloud_request=False,
            company_profile=corp_profile
        ))
        sys_content = next((m for m in res_dup["messages"] if m.get("role") == "system"), None)["content"]
        self.assertEqual(sys_content.count("[PERFIL E IDENTIDAD CORPORATIVA"), 1)

        # Si company_profile está deshabilitado
        disabled_corp = {"enabled": False, "company_name": "NoInyectar"}
        data_clean = {
            "messages": [
                {"role": "user", "content": "Consulta limpia"}
            ]
        }
        res_clean = asyncio.run(enrich_chat_payload(
            data_clean,
            actual_model="gemma",
            is_cloud_request=False,
            company_profile=disabled_corp
        ))
        sys_clean = next((m for m in res_clean["messages"] if m.get("role") == "system"), None)
        if sys_clean:
            self.assertNotIn("[PERFIL E IDENTIDAD CORPORATIVA", sys_clean["content"])

    def test_handle_pdf_generation_company_fallback(self):
        import asyncio
        from unittest.mock import patch, AsyncMock, MagicMock
        from gateway.tools.pdf_generator import handle_pdf_generation

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b'{"title": "Reporte Anual", "markdown_content": "# Contenido"}')
        mock_request.headers = {"host": "127.0.0.1:8000"}
        mock_request.url.scheme = "http"

        key_doc = {
            "name": "Cliente Clave",
            "company_profile": {
                "enabled": True,
                "company_name": "Acme Industries S.A."
            }
        }

        with patch("pdf_engine.create_pdf_from_markdown") as mock_create_pdf:
            mock_create_pdf.return_value = {"success": True, "download_url": "/api/tools/pdf/123"}
            res = asyncio.run(handle_pdf_generation(mock_request, gateway_port=8000, key_doc=key_doc))
            self.assertEqual(res.status_code, 200)
            mock_create_pdf.assert_called_once()
            _, kwargs = mock_create_pdf.call_args
            self.assertEqual(kwargs.get("company_name"), "Acme Industries S.A.")

        # Si viene company_name explícito en tool_data, debe priorizarse el explícito
        mock_req_explicit = MagicMock()
        mock_req_explicit.body = AsyncMock(return_value=b'{"title": "Reporte", "markdown_content": "# Contenido", "company_name": "Empresa Especial"}')
        mock_req_explicit.headers = {"host": "127.0.0.1:8000"}
        mock_req_explicit.url.scheme = "http"

        with patch("pdf_engine.create_pdf_from_markdown") as mock_create_pdf:
            mock_create_pdf.return_value = {"success": True, "download_url": "/api/tools/pdf/123"}
            res = asyncio.run(handle_pdf_generation(mock_req_explicit, gateway_port=8000, key_doc=key_doc))
            self.assertEqual(res.status_code, 200)
            _, kwargs = mock_create_pdf.call_args
            self.assertEqual(kwargs.get("company_name"), "Empresa Especial")

    def test_enrich_chat_payload_multi_tenant_rag(self):
        import asyncio
        from unittest.mock import patch, MagicMock
        from gateway.core.alignment_engine import enrich_chat_payload

        payload = {
            "messages": [
                {"role": "user", "content": "¿Cuáles son las normas internas de soporte?"}
            ]
        }

        with patch("rag_engine.get_rag_settings") as mock_settings, \
             patch("rag_engine.find_documents_by_fuzzy_title") as mock_fuzzy, \
             patch("rag_engine.search_knowledge_base") as mock_search, \
             patch("rag_engine.format_rag_context_for_llm") as mock_format:

            mock_settings.return_value = {"enabled": True}
            mock_fuzzy.return_value = []
            mock_search.return_value = [{"text": "Fragmento de soporte", "doc_title": "Manual", "score": 0.8}]
            mock_format.return_value = "Fragmento de soporte para Tech Support"

            res = asyncio.run(enrich_chat_payload(
                payload,
                actual_model="gemma",
                is_cloud_request=False,
                apply_rag_injection=True,
                company_profile={"rag_table": "kb_tech_support_argentina"}
            ))

            mock_fuzzy.assert_called_once_with(
                "¿Cuáles son las normas internas de soporte?",
                table_name="kb_tech_support_argentina"
            )
            mock_search.assert_called_once()
            _, kwargs = mock_search.call_args
            self.assertEqual(kwargs.get("table_name"), "kb_tech_support_argentina")

            sys_msg = next((m for m in res["messages"] if m.get("role") == "system"), None)
            self.assertIsNotNone(sys_msg)
            self.assertIn("LANCEDB - KB_TECH_SUPPORT_ARGENTINA", sys_msg["content"])

    def test_handle_rag_endpoints_multi_tenant(self):
        import asyncio
        from unittest.mock import patch, MagicMock
        from gateway.tools.rag_endpoints import handle_rag_search

        mock_request = MagicMock()
        mock_request.query_params = {}
        body = b'{"query": "procedimiento operativo"}'
        key_doc = {
            "name": "Tech Support Key",
            "company_profile": {"rag_table": "kb_tech_support_argentina"}
        }

        with patch("rag_engine.get_rag_settings") as mock_sett, \
             patch("rag_engine.search_knowledge_base") as mock_search, \
             patch("rag_engine.format_rag_context_for_llm") as mock_fmt:

            mock_sett.return_value = {"enabled": True}
            mock_search.return_value = [{"text": "Procedimiento ABC", "score": 0.9}]
            mock_fmt.return_value = "Contexto ABC"

            res = asyncio.run(handle_rag_search(mock_request, body, key_doc=key_doc))
            self.assertEqual(res.status_code, 200)
            mock_search.assert_called_once()
            _, kwargs = mock_search.call_args
            self.assertEqual(kwargs.get("table_name"), "kb_tech_support_argentina")

            import json
            data = json.loads(res.body.decode("utf-8"))
            self.assertEqual(data.get("table_name"), "kb_tech_support_argentina")


if __name__ == "__main__":
    unittest.main()



