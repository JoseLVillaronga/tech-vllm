import os
import re
import requests
from pathlib import Path
from flask import Blueprint, request, jsonify, Response
from dashboard.core import parse_env_to_dict, BACKEND_PORTS, REPO_ROOT

tests_bp = Blueprint("tests", __name__)

@tests_bp.route("/api/test/chat", methods=["POST"])
def api_test_chat():
    """Proxy interactivo para probar el endpoint del Chat de LLM."""
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY") or os.getenv("API_KEY", "")
    
    data = request.json or {}
    prompt = data.get("prompt", "¡Hola!")
    model = data.get("model") or current_vars.get("MODEL", "google/gemma-4-E4B-it")
    max_tokens = int(data.get("max_tokens", 400))
    
    port = BACKEND_PORTS.get("gemma", 18000)
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio Gemma (puerto {port}): {str(e)}"}), 502


@tests_bp.route("/api/test/transcribe", methods=["POST"])
def api_test_transcribe():
    """Proxy para subir un audio y obtener la transcripción vía Whisper."""
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY") or os.getenv("API_KEY", "")
    
    if "file" not in request.files:
        return jsonify({"error": "No se subió ningún archivo"}), 400
        
    audio_file = request.files["file"]
    port = BACKEND_PORTS.get("whisper", 18001)
    url = f"http://127.0.0.1:{port}/v1/audio/transcriptions"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    files = {
        "file": (audio_file.filename, audio_file.read(), audio_file.content_type or "audio/wav")
    }
    data = {
        "model": "openai/whisper-large-v3-turbo"
    }
    
    try:
        res = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio Whisper (puerto {port}): {str(e)}"}), 502


@tests_bp.route("/api/test/speech", methods=["POST"])
def api_test_speech():
    """Proxy para generar voz mediante F5-TTS y transmitir el audio resultante."""
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY") or os.getenv("API_KEY", "")
    
    data = request.json or {}
    text = data.get("text", "Hola, esta es una prueba de voz.")
    voice = data.get("voice", "alloy")
    
    port = BACKEND_PORTS.get("tts", 18002)
    url = f"http://127.0.0.1:{port}/v1/audio/speech"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": voice,
        "response_format": "mp3"
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        if res.status_code == 200:
            return Response(res.content, mimetype="audio/mpeg")
        else:
            return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio F5-TTS (puerto {port}): {str(e)}"}), 502


@tests_bp.route("/api/test/diarize", methods=["POST"])
def api_test_diarize():
    """Proxy para subir un audio y obtener la diarización de hablantes vía PyAnnote."""
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY") or os.getenv("API_KEY", "")
    
    if "file" not in request.files:
        return jsonify({"error": "No se subió ningún archivo"}), 400
        
    audio_file = request.files["file"]
    port = BACKEND_PORTS.get("diarization", 18003)
    url = f"http://127.0.0.1:{port}/v1/audio/diarize"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    files = {
        "file": (audio_file.filename, audio_file.read(), audio_file.content_type or "audio/wav")
    }
    
    try:
        res = requests.post(url, headers=headers, files=files, timeout=60)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio de Diarización (puerto {port}): {str(e)}"}), 502


@tests_bp.route("/api/test/image", methods=["POST"])
def api_test_image():
    """Proxy interactivo para probar la generación de imágenes."""
    current_vars = parse_env_to_dict()
    api_key = current_vars.get("API_KEY") or os.getenv("API_KEY", "")
    
    data = request.json or {}
    prompt = data.get("prompt", "A cute futuristic robot in high-tech laboratory")
    size = data.get("size", "512x512")
    
    port = BACKEND_PORTS.get("image", 18004)
    url = f"http://127.0.0.1:{port}/v1/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "prompt": prompt,
        "size": size,
        "n": 1,
        "response_format": "url"
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=120)
        return Response(res.text, status=res.status_code, content_type="application/json")
    except Exception as e:
        return jsonify({"error": f"No se pudo conectar al servicio de Generación de Imágenes (puerto {port}): {str(e)}"}), 502


@tests_bp.route("/api/test/infoleg", methods=["POST"])
def api_test_infoleg():
    """Extrae y convierte normativas oficiales de InfoLEG a Markdown jerárquico."""
    data = request.get_json() or {}
    raw_url = data.get("url", "").strip()
    if not raw_url:
        return jsonify({"success": False, "error": "Debe especificar una URL o un ID numérico de InfoLEG válido."}), 400

    custom_title = data.get("title", "").strip() or None
    prefer_updated = bool(data.get("prefer_updated", True))
    save_to_disk = bool(data.get("save_to_disk", True))

    try:
        from scripts.fetch_infoleg import InfoLegFetcher, InfoLegParser, sanitize_filename

        fetcher = InfoLegFetcher()
        doc_parser = InfoLegParser()

        html, meta, text_url = fetcher.resolve_full_text(raw_url, prefer_updated=prefer_updated)

        doc_title = custom_title or meta.get("titulo_oficial") or meta.get("tipo_numero") or "Documento_InfoLEG"
        markdown_content = doc_parser.generate_markdown(html, meta, custom_title=doc_title)

        safe_filename = sanitize_filename(doc_title)
        if not safe_filename.endswith(".md"):
            safe_filename += ".md"

        output_path_str = None
        if save_to_disk:
            output_dir = REPO_ROOT / "scripts" / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / safe_filename
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            output_path_str = str(output_path)

        size_kb = round(len(markdown_content.encode("utf-8")) / 1024, 1)
        lines_count = len(markdown_content.splitlines())
        art_count = len(re.findall(r"\*\*ART[IÍ]CULO\s+\d+", markdown_content, re.IGNORECASE))

        return jsonify({
            "success": True,
            "filename": safe_filename,
            "content": markdown_content,
            "metadata": {
                "id": meta.get("id"),
                "tipo_numero": meta.get("tipo_numero"),
                "fecha": meta.get("fecha"),
                "boletin_oficial": meta.get("boletin_oficial"),
                "tema": meta.get("tema"),
                "resumen": meta.get("resumen"),
                "texto_url": text_url,
                "saved_path": output_path_str
            },
            "stats": {
                "articles": art_count,
                "lines": lines_count,
                "size_kb": size_kb
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Error extrayendo de InfoLEG: {str(e)}"}), 500
