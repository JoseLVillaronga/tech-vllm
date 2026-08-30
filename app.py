import os
import sys
import subprocess
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

from config import API_KEY

def main():
    # Obtener valores desde .env con valores por defecto
    hf_token = os.getenv("HF_TOKEN")
    api_key = API_KEY
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
        "--trust-remote-code",
        "--enable-chunked-prefill",
        "--max-num-batched-tokens", str(max_num_batched_tokens),
        "--api-key", api_key
    ]

    # Parsers específicos según la familia del modelo
    model_lower = model.lower()
    if "gemma" in model_lower:
        cmd.extend([
            "--tool-call-parser", "gemma4",
            "--reasoning-parser", "gemma4",
            "--enable-auto-tool-choice"
        ])
    elif "qwen" in model_lower:
        cmd.extend([
            "--tool-call-parser", "hermes",
            "--enable-auto-tool-choice"
        ])
    elif "deepseek" in model_lower:
        cmd.extend([
            "--tool-call-parser", "hermes",
            "--enable-auto-tool-choice"
        ])
        if "r1" in model_lower or "reasoner" in model_lower:
            cmd.extend(["--reasoning-parser", "deepseek_r1"])
    elif "mistral" in model_lower:
        cmd.extend([
            "--tool-call-parser", "mistral",
            "--enable-auto-tool-choice"
        ])
    elif "llama" in model_lower:
        cmd.extend([
            "--tool-call-parser", "llama3_json",
            "--enable-auto-tool-choice"
        ])
    elif "glm" in model_lower:
        cmd.extend([
            "--tool-call-parser", "glm47",
            "--reasoning-parser", "deepseek_r1",
            "--enable-auto-tool-choice"
        ])
    else:
        # Fallback estándar para modelos compatibles con OpenAI / Function Calling
        cmd.extend([
            "--tool-call-parser", "hermes",
            "--enable-auto-tool-choice"
        ])

    # Configurar LoRA si está habilitado en .env, el adaptador está completamente descargado y el modelo es compatible (Gemma)
    lora_env = os.getenv("LORA", "True").strip().lower() in ("true", "1", "yes")
    lora_dir = os.getenv("LORA_DIR", "/home/jose/modelos/loras/gemma-4-E4B-opus-reasoning-claude-code-lora")
    has_active_lora = lora_env and "gemma" in model.lower() and os.path.exists(os.path.join(lora_dir, "adapter_config.json"))
    if has_active_lora:
        cmd.extend([
            "--enable-lora",
            "--lora-modules", f"gemma-4-reasoning={lora_dir}",
            "--max-loras", "4",
            "--max-lora-rank", "64"
        ])

    # Configurar resolución condicional del backend de atención (FlashInfer vs FlashAttention)
    flashinfer_families = ["gemma", "qwen", "llama", "mistral", "deepseek", "glm"]
    is_gqa_model = any(f in model.lower() for f in flashinfer_families)
    user_backend_pref = os.getenv("ATTENTION_BACKEND", "auto").strip().lower()

    if user_backend_pref == "flashinfer":
        selected_backend = "FLASHINFER"
        backend_reason = "Manual (.env)"
    elif user_backend_pref in ("flash_attn", "flashattention"):
        selected_backend = "FLASH_ATTN"
        backend_reason = "Manual (.env)"
    else:  # Modo 'auto'
        if has_active_lora:
            selected_backend = "FLASH_ATTN"
            backend_reason = "LoRA activo -> FlashAttention seguro"
        elif is_gqa_model:
            selected_backend = "FLASHINFER"
            backend_reason = "Modelo GQA compatible sin LoRA -> FlashInfer acelerado"
        else:
            selected_backend = "FLASH_ATTN"
            backend_reason = "Estándar -> FlashAttention"

    os.environ["VLLM_ATTENTION_BACKEND"] = selected_backend

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
    print(f"⚡ Backend de Atención: {selected_backend} ({backend_reason})")
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
