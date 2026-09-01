import os
import sys
import asyncio
import uvicorn
from pymongo import MongoClient

from config import get_mongo_uri, MONGO_DB
from gateway.core.ip_rules import sync_ip_rules_loop
from gateway.core.alignment_engine import sync_alignment_settings_loop
from gateway.cloud.cloud_sync import sync_cloud_providers_loop
from gateway.proxy.proxy_factory import create_proxy_app, close_http_client


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


async def run_servers():
    """
    Inicializa índices en MongoDB y levanta concurrentemente los 7 servidores
    proxy en los puertos 8000, 8001, 8002, 8003, 8005, 8006 y 8020.
    """
    try:
        db = get_db()
        db.ip_rules.create_index("expires_at", expireAfterSeconds=0)
        db.usage_logs.create_index("timestamp", expireAfterSeconds=15552000)
        db.blocked_requests.create_index("timestamp", expireAfterSeconds=15552000)
        print("💾 MongoDB: Índices TTL verificados en ip_rules, usage_logs y blocked_requests.", flush=True)
    except Exception as e:
        print(f"⚠️ Error al inicializar índices de MongoDB en Gateway startup: {e}", file=sys.stderr, flush=True)

    gemma_port = int(os.getenv("GEMMA_BACKEND_PORT", "18000"))
    whisper_port = int(os.getenv("WHISPER_BACKEND_PORT", "18001"))
    tts_port = int(os.getenv("TTS_BACKEND_PORT", "18002"))
    diarization_port = int(os.getenv("DIARIZATION_BACKEND_PORT", "18003"))
    image_port = int(os.getenv("IMAGE_BACKEND_PORT", "18004"))
    embeddings_port = int(os.getenv("EMBEDDINGS_BACKEND_PORT", "18005"))
    image_gateway_port = int(os.getenv("IMAGE_GATEWAY_PORT", "8006"))
    docling_port = int(os.getenv("DOCLING_BACKEND_PORT", "5020"))
    docling_gateway_port = int(os.getenv("DOCLING_GATEWAY_PORT", "8020"))

    whisper_fallback_port = int(os.getenv("STT_FALLBACK_PORT", "18011"))
    tts_fallback_port = int(os.getenv("TTS_FALLBACK_PORT", "18012"))

    gemma_app = create_proxy_app("gemma", gemma_port)
    whisper_app = create_proxy_app("whisper", whisper_port, fallback_port=whisper_fallback_port)
    tts_app = create_proxy_app("tts", tts_port, fallback_port=tts_fallback_port)
    diarization_app = create_proxy_app("diarization", diarization_port)
    embeddings_app = create_proxy_app("embeddings", embeddings_port)
    image_app = create_proxy_app("image", image_port)
    docling_app = create_proxy_app("docling", docling_port)

    config_gemma = uvicorn.Config(gemma_app, host="0.0.0.0", port=8000, log_level="warning")
    config_whisper = uvicorn.Config(whisper_app, host="0.0.0.0", port=8001, log_level="warning")
    config_tts = uvicorn.Config(tts_app, host="0.0.0.0", port=8002, log_level="warning")
    config_diarization = uvicorn.Config(diarization_app, host="0.0.0.0", port=8003, log_level="warning")
    config_embeddings = uvicorn.Config(embeddings_app, host="0.0.0.0", port=8005, log_level="warning")
    config_image = uvicorn.Config(image_app, host="0.0.0.0", port=image_gateway_port, log_level="warning")
    config_docling = uvicorn.Config(docling_app, host="0.0.0.0", port=docling_gateway_port, log_level="warning")

    server_gemma = uvicorn.Server(config_gemma)
    server_whisper = uvicorn.Server(config_whisper)
    server_tts = uvicorn.Server(config_tts)
    server_diarization = uvicorn.Server(config_diarization)
    server_embeddings = uvicorn.Server(config_embeddings)
    server_image = uvicorn.Server(config_image)
    server_docling = uvicorn.Server(config_docling)

    print("=" * 60)
    print("🛡️ Iniciando Gateway Modular de Autenticación y Proxy...")
    print(f"🟢 Gemma Proxy:       8000 -> {gemma_port}")
    print(f"🟢 Whisper Proxy:     8001 -> {whisper_port} (Fallback CPU: {whisper_fallback_port})")
    print(f"🟢 F5-TTS Proxy:       8002 -> {tts_port} (Fallback CPU: {tts_fallback_port})")
    print(f"🟢 Diarización Proxy: 8003 -> {diarization_port}")
    print(f"🟢 Embeddings Proxy:  8005 -> {embeddings_port}")
    print(f"🟢 Imagen Proxy:      {image_gateway_port} -> {image_port}")
    print(f"🟢 Docling Proxy:     {docling_gateway_port} -> {docling_port}")
    print("=" * 60)

    try:
        await asyncio.gather(
            sync_ip_rules_loop(),
            sync_alignment_settings_loop(),
            sync_cloud_providers_loop(),
            server_gemma.serve(),
            server_whisper.serve(),
            server_tts.serve(),
            server_diarization.serve(),
            server_embeddings.serve(),
            server_image.serve(),
            server_docling.serve()
        )
    finally:
        await close_http_client()


def main():
    try:
        asyncio.run(run_servers())
    except KeyboardInterrupt:
        print("\n👋 Gateway detenido por el usuario.")


if __name__ == "__main__":
    main()
