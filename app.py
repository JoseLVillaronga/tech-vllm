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
    host = "127.0.0.1" # Forzar localhost para seguridad (detrás de gateway)
    port = os.getenv("GEMMA_BACKEND_PORT", "18000")
    model = os.getenv("MODEL", "nvidia/Gemma-4-26B-A4B-NVFP4")
    gpu_memory_utilization = os.getenv("GPU_MEMORY_UTILIZATION", "0.90")
    max_model_len = os.getenv("MAX_MODEL_LEN", "16384")
    max_num_seqs = os.getenv("MAX_NUM_SEQS", "64")
    kv_cache_dtype = os.getenv("KV_CACHE_DTYPE", "bfloat16")
    swap_space = os.getenv("SWAP_SPACE", "0")
    quantization = os.getenv("QUANTIZATION")
    max_num_batched_tokens = os.getenv("MAX_NUM_BATCHED_TOKENS", "4096")

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
        "--enable-chunked-prefill",
        "--max-num-batched-tokens", str(max_num_batched_tokens),
        "--api-key", api_key
    ]

    # Configurar LoRA si está habilitado en .env, el adaptador está completamente descargado y el modelo es compatible (Gemma)
    lora_env = os.getenv("LORA", "True").strip().lower() in ("true", "1", "yes")
    lora_dir = os.getenv("LORA_DIR", "/home/jose/modelos/loras/gemma-4-E4B-opus-reasoning-claude-code-lora")
    if lora_env and "gemma" in model.lower() and os.path.exists(os.path.join(lora_dir, "adapter_config.json")):
        cmd.extend([
            "--enable-lora",
            "--lora-modules", f"gemma-4-reasoning={lora_dir}",
            "--max-loras", "4",
            "--max-lora-rank", "64"
        ])

    # Agregar --quantization si está definido en .env
    if quantization:
        cmd.extend(["--quantization", quantization])

    # Solo agregar --cpu-offload-gb si swap_space es mayor a 0
    if float(swap_space) > 0:
        cmd.extend(["--cpu-offload-gb", str(swap_space)])

    print("=" * 60)
    print("🚀 Iniciando servidor vLLM OpenAI API...")
    print(f"📦 Modelo: {model}")
    print(f"🌐 Dirección: http://{host}:{port}")
    print(f"🧠 VRAM reservada: {float(gpu_memory_utilization)*100:.0f}% (~{float(gpu_memory_utilization)*24:.1f} GB de 24 GB) | Libre: ~{(1-float(gpu_memory_utilization))*24:.1f} GB")
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
