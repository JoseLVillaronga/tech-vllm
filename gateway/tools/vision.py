import os
import sys
import io
import json
import base64
import mimetypes
import hashlib
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import Request, Response

from config import env

# Alias unificado hacia config.env
get_env_setting = env

# Caché en memoria para extracciones OCR / visuales (evita re-procesar en hilos multi-turno)
_VISION_CACHE: Dict[str, Dict[str, Any]] = {}
_MAX_VISION_CACHE_SIZE = 256

DEFAULT_VISION_PROMPT = (
    "Analiza la imagen y genera tu respuesta siguiendo estrictamente esta estructura:\n"
    "1. TRANSCRIPCIÓN Y DATOS: Transcribe de forma exhaustiva y exacta todo el texto, tablas y números visibles preservando su orden.\n"
    "2. DESCRIPCIÓN VISUAL: Describe brevemente los elementos visuales, diagramas, fotos, estructura o figuras presentes."
)


async def _prepare_image_data_uri_async(image_input: str) -> Optional[str]:
    """
    Convierte una ruta local, URL o base64 en un Data URI válido (data:image/...;base64,...).
    Si es una URL HTTP/HTTPS (ej: servida por Open-WebUI o externa), la descarga
    y convierte a base64 para evitar errores de red o resolución en llama-server.
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
            base64.b64decode(image_input[:100], validate=True)
            return f"data:image/jpeg;base64,{image_input}"
        except Exception:
            pass

    # Caso 4: URL http/https (descargar y convertir a base64 para seguridad local)
    if image_input.startswith("http://") or image_input.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
                r = await client.get(image_input)
                if r.status_code == 200:
                    mime = r.headers.get("content-type", "image/png")
                    encoded = base64.b64encode(r.content).decode("utf-8")
                    return f"data:{mime};base64,{encoded}"
        except Exception as net_err:
            print(f"⚠️ Error descargando imagen desde URL {image_input}: {net_err}", file=sys.stderr, flush=True)
            return image_input

    return None


def optimize_image_resolution_for_vit(
    data_uri: str,
    min_dimension: int = 512,
    min_area: int = 512 * 512,
    max_scale: float = 8.0
) -> str:
    """
    Normaliza y reescala automáticamente imágenes de baja resolución o recortes pequeños
    para el Vision Transformer (ViT) de Qwen2.5-VL.
    Evalúa tanto la dimensión mínima (min(ancho, alto) < min_dimension) como el área total
    (ancho * alto < min_area). Si se cumple alguna, reescala preservando la relación de aspecto
    con filtro Lanczos. Esto previene que el ViT genere un número insuficiente de tokens
    espaciales (<100) y falle al transcribir textos y números finos.
    """
    if not data_uri or not isinstance(data_uri, str) or not data_uri.startswith("data:image/"):
        return data_uri

    try:
        from PIL import Image

        parts = data_uri.split(";base64,", 1)
        if len(parts) != 2:
            return data_uri

        header, b64_payload = parts
        raw_bytes = base64.b64decode(b64_payload)
        img = Image.open(io.BytesIO(raw_bytes))
        w, h = img.size

        current_area = w * h
        needs_resize = (min(w, h) < min_dimension) or (current_area < min_area)

        if needs_resize:
            scale_dim = min_dimension / max(min(w, h), 1)
            scale_area = (min_area / max(current_area, 1)) ** 0.5
            scale = min(max(scale_dim, scale_area), max_scale)

            new_w = max(round(w * scale), 1)
            new_h = max(round(h * scale), 1)
            if scale < max_scale and min(new_w, new_h) < min_dimension:
                if new_w <= new_h:
                    new_w = min_dimension
                else:
                    new_h = min_dimension

            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            new_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            print(f"🔍 Gateway Vision Bridge: Imagen reescalada de {w}x{h} (área {current_area}px²) a {new_w}x{new_h} (área {new_w*new_h}px²) (optimización ViT tokens)", file=sys.stderr, flush=True)
            return f"data:image/png;base64,{new_b64}"

    except Exception as err:
        print(f"⚠️ Gateway Vision Bridge: Error al verificar/reescalar resolución de imagen: {err}", file=sys.stderr, flush=True)

    return data_uri



async def analyze_image_with_vision_backend(
    image_uri: str,
    prompt: Optional[str] = None,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Realiza la llamada multimodal a la instancia de visión de llama-server en RAM (:18200).
    Cuenta con caché en memoria LRU por hash SHA-256 para evitar re-análisis en hilos multi-turno.
    """
    image_uri = optimize_image_resolution_for_vit(image_uri)
    vision_port = int(get_env_setting("VISION_BACKEND_PORT", "18200"))
    vision_alias = get_env_setting("VISION_ALIAS", "Qwen2.5-VL-3B-Instruct")
    auth_key = get_env_setting("API_KEY", "")
    backend_url = f"http://127.0.0.1:{vision_port}/v1/chat/completions"

    instruction = prompt.strip() if prompt and prompt.strip() else DEFAULT_VISION_PROMPT

    # Verificación en caché SHA-256 para evitar re-análisis en hilos conversacionales continuos
    cache_key = hashlib.sha256(f"{image_uri}_{instruction}".encode("utf-8")).hexdigest()
    if cache_key in _VISION_CACHE:
        cached_res = dict(_VISION_CACHE[cache_key])
        cached_res["cached"] = True
        print(f"⚡ Gateway Vision Bridge: Imagen recuperada de caché en memoria (SHA-256: {cache_key[:8]}), omitiendo re-inferencia en CPU", file=sys.stderr, flush=True)
        return cached_res

    payload = {
        "model": vision_alias,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_uri}},
                    {"type": "text", "text": instruction}
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

            result_data = {
                "success": True,
                "analysis": content,
                "text": content,
                "model": vision_alias,
                "usage": res_json.get("usage", {}),
                "cached": False
            }

            # Guardar en caché LRU en memoria
            if len(_VISION_CACHE) >= _MAX_VISION_CACHE_SIZE:
                _VISION_CACHE.pop(next(iter(_VISION_CACHE)))
            _VISION_CACHE[cache_key] = result_data

            return result_data
        else:
            err_msg = f"Vision backend HTTP {resp.status_code}: {resp.text}"
            print(f"⚠️ {err_msg}", file=sys.stderr, flush=True)
            return {
                "success": False,
                "error": err_msg,
                "analysis": ""
            }


async def bridge_multimodal_messages(messages: List[Dict[str, Any]]) -> bool:
    """
    Puente de Visión Multimodal Transparente (Vision Bridge):
    Detecta bloques 'image_url' en mensajes dirigidos a modelos de solo texto (como Gemma 4 12B IT).
    Invoca al microservicio de visión desacoplado en RAM (Qwen2.5-VL en :18200),
    obtiene la transcripción OCR y análisis visual fiel, y reemplaza los bloques 'image_url'
    por texto estructurado limpio.
    
    Esto evita que llama-server falle con 'image input is not supported - hint: provide mmproj'
    y provee capacidad multimodal automática a modelos de texto sin tocar la GPU.
    """
    if not messages or not isinstance(messages, list):
        return False

    transformed_any = False

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue

        has_image = any(isinstance(p, dict) and p.get("type") == "image_url" for p in content)
        if not has_image:
            continue

        total_images = sum(1 for p in content if isinstance(p, dict) and p.get("type") == "image_url")
        image_counter = 0

        visual_blocks = []
        user_text_blocks = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "image_url":
                image_counter += 1
                raw_url = part.get("image_url", {})
                img_src = raw_url.get("url") if isinstance(raw_url, dict) else str(raw_url)
                data_uri = await _prepare_image_data_uri_async(img_src)
                if data_uri:
                    print("👁️ Gateway Vision Bridge: Analizando imagen adjunta con Qwen2.5-VL en RAM (:18200)...", file=sys.stderr, flush=True)
                    res = await analyze_image_with_vision_backend(
                        data_uri,
                        prompt=(
                            "Analiza la imagen y genera tu respuesta siguiendo estrictamente esta estructura:\n"
                            "1. TRANSCRIPCIÓN Y DATOS: Transcribe de forma exhaustiva y exacta todo el texto, títulos, números de remitos, tablas y números visibles.\n"
                            "2. DESCRIPCIÓN VISUAL: Describe brevemente los elementos visuales, diagramas, fotos, estructura o figuras presentes."
                        )
                    )
                    if res.get("success"):
                        ocr_text = res.get("analysis") or res.get("text") or ""
                        print(f"✅ Gateway Vision Bridge: Extracción completada ({len(ocr_text)} caracteres)", file=sys.stderr, flush=True)
                        img_label = f" (Imagen {image_counter} de {total_images})" if total_images > 1 else ""
                        open_tag = f'<imagen_adjunta indice="{image_counter}" total="{total_images}">' if total_images > 1 else "<imagen_adjunta>"
                        visual_blocks.append(
                            f"{open_tag}\n"
                            f"[AVISO DEL SISTEMA]: El usuario ha adjuntado una imagen{img_label} a la conversación. El motor de visión local (Qwen2.5-VL en RAM) la ha procesado previamente y ha generado la siguiente transcripción fiel y descripción visual:\n\n"
                            f"<contenido_visual_extraido>\n"
                            f"{ocr_text}\n"
                            f"</contenido_visual_extraido>\n\n"
                            f"INSTRUCCIÓN PARA EL MODELO: Responde directamente a la solicitud del usuario utilizando la información anterior como la visualización fidedigna de la imagen adjunta. NUNCA digas que no recibiste la imagen.\n"
                            f"</imagen_adjunta>"
                        )
                        transformed_any = True
                    else:
                        visual_blocks.append(f"<imagen_adjunta>\n[AVISO DEL SISTEMA]: No se pudo procesar la imagen adjunta: {res.get('error', 'Error desconocido')}\n</imagen_adjunta>")
                else:
                    visual_blocks.append("<imagen_adjunta>\n[AVISO DEL SISTEMA]: Formato de imagen adjunta no reconocido o inaccesible.\n</imagen_adjunta>")
            elif part.get("type") == "text":
                txt = part.get("text", "").strip()
                if txt:
                    user_text_blocks.append(txt)

        # Reensamblar el mensaje: primero los bloques de imagen con tags, luego el texto del usuario
        final_parts = []
        if visual_blocks:
            final_parts.extend(visual_blocks)
        if user_text_blocks:
            final_parts.extend(user_text_blocks)

        msg["content"] = "\n\n".join(final_parts).strip()

    return transformed_any


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

            image_uri = await _prepare_image_data_uri_async(raw_image)

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
