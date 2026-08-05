import os
import sys
import subprocess
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def main():
    # Obtener valores desde .env con valores por defecto
    hf_token = os.getenv("HF_TOKEN")
    api_key = os.getenv("API_KEY", "token-abc123")
    host = os.getenv("HOST", "0.0.0.0")
    port = os.getenv("PORT", "8000")
    model = os.getenv("MODEL", "nvidia/Gemma-4-26B-A4B-NVFP4")
    gpu_memory_utilization = os.getenv("GPU_MEMORY_UTILIZATION", "0.90")
    max_model_len = os.getenv("MAX_MODEL_LEN", "16384")
    max_num_seqs = os.getenv("MAX_NUM_SEQS", "64")
    kv_cache_dtype = os.getenv("KV_CACHE_DTYPE", "bfloat16")
    swap_space = os.getenv("SWAP_SPACE", "0")

    # Exportar HF_TOKEN si está definido
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token

    # Construir el comando vLLM
    cmd = [
        sys.executable,
        "-m", "vllm.entrypoints.openai.api_server",
        "--host", host,
        "--port", str(port),
        "--model", model,
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--max-model-len", str(max_model_len),
        "--max-num-seqs", str(max_num_seqs),
        "--kv-cache-dtype", kv_cache_dtype,
        "--tool-call-parser", "gemma4",
        "--reasoning-parser", "gemma4",
        "--enable-auto-tool-choice",
        "--trust-remote-code",
        "--api-key", api_key
    ]

    # Solo agregar --cpu-offload-gb si swap_space es mayor a 0
    if float(swap_space) > 0:
        cmd.extend(["--cpu-offload-gb", str(swap_space)])

    print("=" * 60)
    print("🚀 Iniciando servidor vLLM OpenAI API...")
    print(f"📦 Modelo: {model}")
    print(f"🌐 Dirección: http://{host}:{port}")
    print(f"💾 CPU Offload GB: {swap_space} GB RAM" if float(swap_space) > 0 else "⚡ CPU Offload: Deshabilitado (Máxima velocidad GPU)")
    print(f"🔑 API Key configurada: {api_key}")
    print("=" * 60 + "\n")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Servidor vLLM detenido por el usuario.")
    except Exception as e:
        print(f"\n❌ Error al ejecutar el servidor vLLM: {e}")

if __name__ == "__main__":
    main()
