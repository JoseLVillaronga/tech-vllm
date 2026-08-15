import os
import sys
from dotenv import load_dotenv
from huggingface_hub import snapshot_download

# Cargar variables de entorno del archivo .env del proyecto
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_dir, ".env")
load_dotenv(dotenv_path)

def main():
    repo_id = "deadbydawn101/gemma-4-E4B-opus-reasoning-claude-code-lora"
    local_dir = "/home/jose/modelos/loras/gemma-4-E4B-opus-reasoning-claude-code-lora"
    hf_token = os.getenv("HF_TOKEN")
    
    print(f"📥 Iniciando la descarga de LoRA: {repo_id}...")
    print(f"📂 Destino local: {local_dir}")
    
    try:
        os.makedirs(local_dir, exist_ok=True)
        # Descargar el repositorio completo del LoRA usando el token de Hugging Face
        snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            token=hf_token,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot"] # Evitar formatos de tensores innecesarios
        )
        print("✅ Descarga del LoRA completada con éxito!")
    except Exception as e:
        print(f"❌ Error al descargar el LoRA: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
