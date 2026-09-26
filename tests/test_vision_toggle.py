import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from starlette.requests import Request
import json
import subprocess
import sys
from pathlib import Path

from gateway.tools.vision import (
    is_vision_enabled,
    analyze_image_with_vision_backend,
    bridge_multimodal_messages,
    handle_vision_analysis,
)

BASE_DIR = Path(__file__).resolve().parent.parent


class TestVisionToggle(unittest.IsolatedAsyncioTestCase):

    def test_is_vision_enabled_truthy_and_falsy(self):
        """Verifica la resolución booleana precisa de VISION_ON."""
        truthy_cases = ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON", True]
        falsy_cases = ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF", False, ""]

        for val in truthy_cases:
            with patch("gateway.tools.vision.get_env_setting", return_value=val):
                self.assertTrue(
                    is_vision_enabled(),
                    f"Se esperaba True para VISION_ON={val}"
                )

        for val in falsy_cases:
            with patch("gateway.tools.vision.get_env_setting", return_value=val):
                self.assertFalse(
                    is_vision_enabled(),
                    f"Se esperaba False para VISION_ON={val}"
                )

    @patch("gateway.tools.vision.is_vision_enabled", return_value=False)
    @patch("httpx.AsyncClient")
    async def test_analyze_image_backend_when_disabled(self, mock_client, mock_enabled):
        """Verifica que si VISION_ON=false, no se realiza ninguna llamada de red y retorna error descriptivo."""
        result = await analyze_image_with_vision_backend("data:image/png;base64,iVBORw0KGgo=")
        self.assertFalse(result["success"])
        self.assertIn("VISION_ON=false", result["error"])
        mock_client.assert_not_called()

    @patch("gateway.tools.vision.is_vision_enabled", return_value=False)
    async def test_bridge_multimodal_messages_local_disabled(self, mock_enabled):
        """Verifica que mensajes multimodales locales se protegen con aviso educado cuando VISION_ON=false."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "¿Qué dice esta imagen?"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="}}
                ]
            }
        ]

        transformed = await bridge_multimodal_messages(messages, is_cloud_request=False, model_name="local/CorpAI-Gen")
        self.assertTrue(transformed)
        self.assertIsInstance(messages[0]["content"], str)
        self.assertIn("VISION_ON=false", messages[0]["content"])
        self.assertIn("[AVISO DEL SISTEMA]", messages[0]["content"])
        self.assertIn("¿Qué dice esta imagen?", messages[0]["content"])

    async def test_bridge_multimodal_messages_cloud_preserves_images(self):
        """Verifica que las peticiones hacia la nube preservan intactos los bloques image_url para procesamiento nativo."""
        original_content = [
            {"type": "text", "text": "Analiza esta imagen con DeepSeek VL"},
            {"type": "image_url", "image_url": {"url": "https://example.com/test.png"}}
        ]
        messages = [
            {
                "role": "user",
                "content": list(original_content)
            }
        ]

        # Con is_cloud_request=True, debe retornar False sin transformar el contenido
        transformed = await bridge_multimodal_messages(messages, is_cloud_request=True, model_name="deepseek-v4-flash-vision-exp")
        self.assertFalse(transformed)
        self.assertEqual(messages[0]["content"], original_content)

    @patch("gateway.tools.vision.is_vision_enabled", return_value=True)
    @patch("gateway.tools.vision.analyze_image_with_vision_backend")
    async def test_bridge_multimodal_messages_local_enabled(self, mock_analyze, mock_enabled):
        """Verifica que cuando VISION_ON=true, el puente transcribe la imagen e inyecta el análisis visual."""
        mock_analyze.return_value = {
            "success": True,
            "analysis": "Transcripción de documento de prueba",
            "cached": False
        }

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Resume este archivo"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="}}
                ]
            }
        ]

        transformed = await bridge_multimodal_messages(messages, is_cloud_request=False, model_name="local/CorpAI-Gen")
        self.assertTrue(transformed)
        self.assertIsInstance(messages[0]["content"], str)
        self.assertIn("Transcripción de documento de prueba", messages[0]["content"])
        self.assertIn("Resume este archivo", messages[0]["content"])
        mock_analyze.assert_called_once()

    @patch("gateway.tools.vision.is_vision_enabled", return_value=False)
    async def test_handle_vision_analysis_disabled_503(self, mock_enabled):
        """Verifica que el endpoint /api/tools/vision responda 503 si VISION_ON=false."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"content-type": "application/json"}
        
        response = await handle_vision_analysis(mock_request)
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.body.decode("utf-8"))
        self.assertFalse(data["success"])
        self.assertIn("VISION_ON=false", data["error"])

    def test_llama_vision_srv_sh_exits_cleanly_when_disabled(self):
        """Verifica que el script llama-vision-srv.sh detecte VISION_ON=false y salga con código 0."""
        script_path = BASE_DIR / "llama-vision-srv.sh"
        if not script_path.exists():
            self.skipTest("llama-vision-srv.sh no encontrado en el directorio base")

        proc = subprocess.run(
            ["bash", str(script_path)],
            env={"VISION_ON": "false", "PATH": "/usr/local/bin:/usr/bin:/bin"},
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Microservicio de visión desactivado por configuración (VISION_ON=false)", proc.stdout)


if __name__ == "__main__":
    unittest.main()
