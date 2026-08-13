import os
import sys
import subprocess
from dotenv import load_dotenv

# Cargar variables de entorno del proyecto
load_dotenv()

def main():
    api_key = os.getenv("API_KEY", "token-abc123")
    host = "127.0.0.1" # Forzar localhost por seguridad (detrás de gateway)
    port = os.getenv("WHISPER_BACKEND_PORT", "18001")
    model = "openai/whisper-large-v3-turbo"
    
    # IMPORTANTE: Limitamos la utilización de VRAM a solo 10% (~2.4 GB)
    # Ya que Whisper es un modelo pequeño (809M params) y no requiere el 90% por defecto.
    gpu_memory_utilization = "0.10"

    # Construir el comando vLLM para servir Whisper
    cmd = [
        sys.executable,
        "-m", "vllm.entrypoints.openai.api_server",
        "--host", host,
        "--port", str(port),
        "--model", model,
        "--gpu-memory-utilization", gpu_memory_utilization,
        "--trust-remote-code",
        "--api-key", api_key
    ]

    print("=" * 60)
    print("🚀 Iniciando servidor vLLM Whisper API...")
    print(f"📦 Modelo: {model}")
    print(f"🌐 Dirección: http://{host}:{port}")
    print(f"🧠 VRAM reservada: {float(gpu_memory_utilization)*100:.0f}% (~{float(gpu_memory_utilization)*24:.1f} GB de 24 GB)")
    print(f"🔑 API Key configurada: {api_key}")
    print("=" * 60 + "\n")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Servidor vLLM Whisper detenido.")
    except Exception as e:
        print(f"\n❌ Error al ejecutar el servidor Whisper: {e}")

if __name__ == "__main__":
    main()
