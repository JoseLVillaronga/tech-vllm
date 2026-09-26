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
    is_local_backend_multimodal,
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

    @patch("gateway.tools.vision.is_local_backend_multimodal", new_callable=AsyncMock, return_value=False)
    @patch("gateway.tools.vision.is_vision_enabled", return_value=False)
    async def test_bridge_multimodal_messages_local_disabled(self, mock_enabled, mock_is_local_mm):
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

    @patch("gateway.tools.vision.is_local_backend_multimodal", new_callable=AsyncMock, return_value=False)
    @patch("gateway.tools.vision.is_vision_enabled", return_value=True)
    @patch("gateway.tools.vision.analyze_image_with_vision_backend")
    async def test_bridge_multimodal_messages_local_enabled(self, mock_analyze, mock_enabled, mock_is_local_mm):
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


    @patch("gateway.tools.vision.is_local_backend_multimodal", return_value=True)
    async def test_bridge_multimodal_messages_delegates_to_native_local_vision(self, mock_local_vision):
        """Verifica que si el backend local cuenta con visión nativa (--mmproj), el Vision Bridge no interviene."""
        original_content = [
            {"type": "text", "text": "Analiza esta imagen con Qwen3.6 nativo"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo="}}
        ]
        messages = [
            {
                "role": "user",
                "content": list(original_content)
            }
        ]

        # No debe transformar los mensajes, permitiendo que llama-server los procese de forma nativa
        transformed = await bridge_multimodal_messages(messages, is_cloud_request=False, model_name="local/CorpAI-Gen")
        self.assertFalse(transformed)
        self.assertEqual(messages[0]["content"], original_content)

    @patch("httpx.AsyncClient")
    async def test_is_local_backend_multimodal_detection(self, mock_client_cls):
        """Verifica la detección dinámica de visión nativa leyendo /props de llama-server."""
        import gateway.tools.vision as vision_mod
        vision_mod._LOCAL_VISION_CAPABLE = None
        vision_mod._LOCAL_VISION_CHECK_TIME = 0.0

        # Caso 1: Backend reporta vision: true
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"modalities": {"vision": True}}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__.return_value = mock_client
        mock_client_cls.return_value = mock_client

        is_capable = await is_local_backend_multimodal()
        self.assertTrue(is_capable)

        # Caso 2: Backend reporta vision: false
        vision_mod._LOCAL_VISION_CAPABLE = None
        vision_mod._LOCAL_VISION_CHECK_TIME = 0.0
        mock_resp.json.return_value = {"modalities": {"vision": False}}

        is_capable = await is_local_backend_multimodal()
        self.assertFalse(is_capable)

    def test_llama_srv_sh_conditional_mmproj_logic(self):
        """Verifica la lógica condicional de --mmproj en llama-srv.sh cuando la variable está comentada vs activa."""
        script_path = BASE_DIR / "llama-srv.sh"
        if not script_path.exists():
            self.skipTest("llama-srv.sh no encontrado")

        # Prueba con bash extrayendo el bloque condicional 5.1
        test_script = """
        RESOLVED_LLAMA_DIR="/tmp/test_llama_dir"
        USER_HOME="/tmp/test_home"
        mkdir -p "${RESOLVED_LLAMA_DIR}/models"
        touch "${RESOLVED_LLAMA_DIR}/models/test-mmproj.gguf"

        test_block() {
            RAW_MMPROJ="$1"
            RAW_MMPROJ="${LLAMA_MMPROJ:-${VISION_MMPROJ:-${LLAMA_MMPROJ_PATH:-}}}"
            MMPROJ_ARGS=()
            if [ -n "${RAW_MMPROJ}" ]; then
                MMPROJ_PATH="${RAW_MMPROJ/\\$LLAMA_DIR/$RESOLVED_LLAMA_DIR}"
                MMPROJ_PATH="${MMPROJ_PATH/\\$HOME/$USER_HOME}"
                if [[ "${MMPROJ_PATH}" == /root* || "${MMPROJ_PATH}" != /* ]]; then
                    MMPROJ_PATH="${RESOLVED_LLAMA_DIR}/models/$(basename "${MMPROJ_PATH}")"
                fi
                if [ -f "${MMPROJ_PATH}" ]; then
                    MMPROJ_ARGS=(--mmproj "${MMPROJ_PATH}")
                fi
            fi
            echo "COUNT:${#MMPROJ_ARGS[@]}"
        }

        # 1. Comentada o vacía -> 0 argumentos agregados
        LLAMA_MMPROJ="" test_block
        # 2. Con archivo existente -> 2 argumentos (--mmproj <ruta>)
        LLAMA_MMPROJ="$RESOLVED_LLAMA_DIR/models/test-mmproj.gguf" test_block
        # 3. Compatible con VISION_MMPROJ
        LLAMA_MMPROJ="" VISION_MMPROJ="$RESOLVED_LLAMA_DIR/models/test-mmproj.gguf" test_block

        rm -rf "${RESOLVED_LLAMA_DIR}"
        """
        proc = subprocess.run(["bash", "-c", test_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(lines[0], "COUNT:0")
        self.assertEqual(lines[1], "COUNT:2")
        self.assertEqual(lines[2], "COUNT:2")


if __name__ == "__main__":
    unittest.main()
