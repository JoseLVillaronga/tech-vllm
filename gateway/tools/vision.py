import os
import sys
import json
import base64
import mimetypes
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import Request, Response

from config import env

# Alias unificado hacia config.env
get_env_setting = env

DEFAULT_VISION_PROMPT = (
    "Analiza detalladamente esta imagen. Si contiene texto, documentos, tablas o recibos, "
    "realiza una transcripción OCR exhaustiva y fiel de todo el texto visible preservando el formato. "
    "Si es un diagrama, gráfico o esquema, describe detalladamente su contenido, componentes, valores y conclusiones."
)


def _prepare_image_data_uri(image_input: str) -> Optional[str]:
    """
    Convierte una ruta local, URL o base64 en un Data URI válido (data:image/...;base64,...).
    """
    if not image_input or not isinstance(image_input, str):
        return None

    image_input = image_input.strip()

    # Caso 1: Ya es un data URI
    if image_input.startswith("data:image/"):
        return image_input

    # Caso 2: Ruta de archivo local
    path_obj = Path(image_input)
    if path_obj.is_file():
        mime_type, _ = mimetypes.guess_type(str(path_obj))
        if not mime_type:
            mime_type = "image/png"
        try:
            with open(path_obj, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
                return f"data:{mime_type};base64,{encoded}"
        except Exception as read_err:
            print(f"⚠️ Error leyendo archivo local de imagen {image_input}: {read_err}", file=sys.stderr, flush=True)
            return None

    # Caso 3: Es una cadena base64 cruda
    if len(image_input) > 100 and not image_input.startswith("http://") and not image_input.startswith("https://"):
        try:
            # Validar si decodifica correctamente
            base64.b64decode(image_input[:100], validate=True)
            return f"data:image/jpeg;base64,{image_input}"
        except Exception:
            pass

    # Caso 4: URL http/https (se pasa directo o se descarga)
    if image_input.startswith("http://") or image_input.startswith("https://"):
        return image_input

    return None


async def analyze_image_with_vision_backend(
    image_uri: str,
    prompt: Optional[str] = None,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Realiza la llamada multimodal a la instancia de visión de llama-server en RAM (:18200).
    """
    vision_port = int(get_env_setting("VISION_BACKEND_PORT", "18200"))
    vision_alias = get_env_setting("VISION_ALIAS", "Qwen2.5-VL-3B-Instruct")
    auth_key = get_env_setting("API_KEY", "token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939")
    backend_url = f"http://127.0.0.1:{vision_port}/v1/chat/completions"

    instruction = prompt.strip() if prompt and prompt.strip() else DEFAULT_VISION_PROMPT

    payload = {
        "model": vision_alias,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {"type": "image_url", "image_url": {"url": image_uri}}
                ]
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.1
    }

    headers = {
        "Authorization": f"Bearer {auth_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(backend_url, headers=headers, json=payload)
        if resp.status_code == 200:
            res_json = resp.json()
            choices = res_json.get("choices", [])
            content = ""
            if choices and isinstance(choices, list):
                msg = choices[0].get("message", {})
                content = msg.get("content", "")
            return {
                "success": True,
                "analysis": content,
                "text": content,
                "model": vision_alias,
                "usage": res_json.get("usage", {})
            }
        else:
            err_msg = f"Vision backend HTTP {resp.status_code}: {resp.text}"
            print(f"⚠️ {err_msg}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": err_msg,
                "analysis": ""
            }


async def handle_vision_analysis(request: Request) -> Response:
    """
    Manejador para el endpoint POST /api/tools/vision (y /v1/tools/vision).
    Soporta multipart/form-data (archivos subidos) y JSON (base64, URL o ruta local).
    """
    try:
        content_type = request.headers.get("content-type", "")
        image_uri = None
        prompt = None

        # Caso A: Multipart form upload
        if "multipart/form-data" in content_type:
            form = await request.form()
            upload_file = form.get("file") or form.get("image") or form.get("files")
            prompt = form.get("prompt") or form.get("question") or form.get("instruccion")
            if upload_file and hasattr(upload_file, "read"):
                file_bytes = await upload_file.read()
                mime = upload_file.content_type or "image/png"
                encoded = base64.b64encode(file_bytes).decode("utf-8")
                image_uri = f"data:{mime};base64,{encoded}"
        # Caso B: JSON payload
        else:
            body_bytes = await request.body()
            data = json.loads(body_bytes) if body_bytes else {}

            # Desenvolver argumentos de Open-WebUI o tool calling si existen
            if "arguments" in data and isinstance(data["arguments"], dict):
                data.update(data["arguments"])
            elif "arguments" in data and isinstance(data["arguments"], str):
                try:
                    arg_obj = json.loads(data["arguments"])
                    if isinstance(arg_obj, dict):
                        data.update(arg_obj)
                except Exception:
                    pass

            raw_image = data.get("image") or data.get("imagen") or data.get("image_url") or data.get("url") or data.get("file_path") or data.get("path")
            prompt = data.get("prompt") or data.get("pregunta") or data.get("instruccion") or data.get("query")

            # Fallback a mensajes previos si vienen en el payload
            if not raw_image and "messages" in data:
                msgs = data["messages"]
                for m in reversed(msgs):
                    c = m.get("content")
                    if isinstance(c, list):
                        for part in c:
                            if isinstance(part, dict) and part.get("type") == "image_url":
                                raw_image = part.get("image_url", {}).get("url")
                                break
                    if raw_image:
                        break

            image_uri = _prepare_image_data_uri(raw_image)

        if not image_uri:
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "No se proporcionó una imagen válida (se requiere archivo, ruta local, URL o base64)."
                }),
                media_type="application/json",
                status_code=400
            )

        result = await analyze_image_with_vision_backend(image_uri, prompt=prompt)
        status_code = 200 if result.get("success") else 502

        return Response(
            content=json.dumps(result),
            media_type="application/json",
            status_code=status_code
        )

    except Exception as exc:
        print(f"⚠️ Error en handle_vision_analysis: {exc}", file=sys.stderr, flush=True)
        return Response(
            content=json.dumps({"success": False, "error": str(exc)}),
            media_type="application/json",
            status_code=500
        )
