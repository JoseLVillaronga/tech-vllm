"""
test_diarization.py — Test de integración y validación para el servicio de Diarización (PyAnnote 3.1).
"""
import os
import unittest
import requests
import wave
import struct
import math
from config import API_KEY as MASTER_KEY


class TestDiarizationService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ALLOW_MASTER_KEY_ON_GATEWAY"] = "true"
        cls.gateway_url = "http://127.0.0.1:8003"
        cls.backend_url = "http://127.0.0.1:18003"
        
        # Obtener clave autorizada para tests desde entorno o desde MongoDB
        test_key = os.getenv("TEST_API_KEY", "")
        if not test_key:
            try:
                from dashboard.core.database import get_db
                db = get_db()
                key_doc = db.api_keys.find_one({"name": "Tests Unitarios", "is_active": True})
                if key_doc and "key" in key_doc:
                    test_key = key_doc["key"]
                db.client.close()
            except Exception:
                pass
        cls.api_key = test_key or MASTER_KEY
        cls.test_wav = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_speech_test.wav")

        os.makedirs(os.path.dirname(cls.test_wav), exist_ok=True)
        # Generar un archivo WAV sintético de prueba
        sample_rate = 16000
        with wave.open(cls.test_wav, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            # 3 segundos de audio modulado
            for i in range(int(sample_rate * 3.0)):
                t = i / sample_rate
                val = int(32767.0 * 0.4 * math.sin(2 * math.pi * 350 * t))
                wav_file.writeframes(struct.pack("<h", val))

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_wav):
            try:
                os.remove(cls.test_wav)
            except Exception:
                pass

    def test_01_backend_health_check(self):
        """Verifica que el servicio backend de diarización esté activo y en buen estado."""
        try:
            resp = requests.get(f"{self.backend_url}/health", timeout=5.0)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("status", data)
            self.assertEqual(data["status"], "healthy")
        except requests.exceptions.ConnectionError:
            self.skipTest("vllm-diarization.service no está escuchando en puerto 18003")

    def test_02_gateway_unauthorized_access(self):
        """Verifica que el Gateway bloquee peticiones sin API Key o con credenciales inválidas."""
        with open(self.test_wav, "rb") as f:
            files = {"file": ("test.wav", f, "audio/wav")}
            resp = requests.post(f"{self.gateway_url}/v1/audio/diarize", files=files, timeout=10.0)
        self.assertEqual(resp.status_code, 401)

    def test_03_gateway_diarization_execution(self):
        """Verifica la ejecución completa de diarización con marcas de tiempo a través del Gateway."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with open(self.test_wav, "rb") as f:
            files = {"file": ("test.wav", f, "audio/wav")}
            try:
                resp = requests.post(
                    f"{self.gateway_url}/v1/audio/diarize",
                    headers=headers,
                    files=files,
                    timeout=30.0
                )
            except requests.exceptions.ConnectionError:
                self.skipTest("Gateway no está escuchando en puerto 8003")

        if resp.status_code in [502, 503]:
            self.skipTest(f"Backend vllm-diarization no disponible (HTTP {resp.status_code})")

        self.assertEqual(resp.status_code, 200, f"Error en diarización: {resp.text}")
        data = resp.json()
        self.assertIn("segments", data)
        self.assertIsInstance(data["segments"], list)


if __name__ == "__main__":
    unittest.main()
