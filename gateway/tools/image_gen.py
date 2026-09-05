import os
import sys
import time
import uuid
import json
import base64
import httpx
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from fastapi import Request, Response, BackgroundTasks, HTTPException, status
from fastapi.responses import JSONResponse

from gateway.telemetry.usage_logger import save_usage_log


# Resolución dinámica del directorio outputs/images respetando Invariante 4 MEA
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "images"


def _resolve_public_base_url(request: Request) -> str:
    """
    Resuelve la URL base pública adecuada (ej: http://127.0.0.1:8000 o https://tu-dominio.com:19000).
    Respeta cabeceras de proxy inverso (X-Forwarded-Proto, X-Forwarded-Host).
    """
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")

    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    # Variable de entorno de URL pública si está configurada
    public_url_env = os.getenv("PUBLIC_GATEWAY_URL")
    if public_url_env:
        return public_url_env.rstrip("/")

    # Fallback al request base_url
    return str(request.base_url).rstrip("/")


async def handle_image_generation_request(
    request: Request,
    body: bytes,
    backend_port: int,
    model_name: str,
    client_ip: str,
    token: str,
    background_tasks: BackgroundTasks
) -> Response:
    """
    Maneja y optimiza peticiones POST /v1/images/generations:
    1. Reenvía la petición al backend local (sd-server en :18004).
    2. Decodifica el Base64 generado y lo persiste en outputs/images/ como archivo PNG.
    3. Inyecta la URL accesible del archivo generado (evitando colapsar la ventana de contexto con 400k+ tokens).
    4. Si el cliente no solicitó explícitamente b64_json, purga el payload base64 gigante.
    5. Registra la telemetría en MongoDB.
    """
    t_start = datetime.now(timezone.utc).replace(tzinfo=None)
    req_json = {}
    if body:
        try:
            req_json = json.loads(body.decode("utf-8", errors="ignore"))
        except Exception:
            pass

    req_format = req_json.get("response_format", "url")
    prompt = req_json.get("prompt", "")

    backend_url = f"http://127.0.0.1:{backend_port}/v1/images/generations"

    headers = {
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(backend_url, headers=headers, content=body)

        if resp.status_code != 200:
            err_body = resp.text
            try:
                err_json = resp.json()
                return JSONResponse(status_code=resp.status_code, content=err_json)
            except Exception:
                return JSONResponse(status_code=resp.status_code, content={"error": err_body})

        res_data = resp.json()
        data_items = res_data.get("data", [])

        # Asegurar existencia del directorio en disco
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        base_url = _resolve_public_base_url(request)

        created_ts = res_data.get("created", int(time.time()))

        for item in data_items:
            b64_str = item.get("b64_json")
            if b64_str:
                try:
                    img_bytes = base64.b64decode(b64_str)
                    img_filename = f"img_{created_ts}_{uuid.uuid4().hex[:8]}.png"
                    img_filepath = OUTPUT_DIR / img_filename
                    img_filepath.write_bytes(img_bytes)

                    public_img_url = f"{base_url}/outputs/images/{img_filename}"
                    item["url"] = public_img_url

                    # Si el cliente pidió formato URL (o no especificó b64_json explícito),
                    # eliminamos la cadena base64 para proteger la ventana de contexto del LLM
                    if req_format != "b64_json":
                        item.pop("b64_json", None)

                except Exception as save_err:
                    print(f"⚠️ Error guardando imagen en disco: {save_err}", file=sys.stderr, flush=True)

        duration_sec = (datetime.now(timezone.utc).replace(tzinfo=None) - t_start).total_seconds()

        # Telemetría de uso
        background_tasks.add_task(
            save_usage_log,
            client_ip,
            token,
            "image",
            "v1/images/generations",
            model_name,
            0,
            0,
            0.0,
            duration_sec
        )

        return JSONResponse(status_code=200, content=res_data)

    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo conectar con el microservicio de generación de imágenes (sd-server en puerto :{backend_port})."
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Tiempo de espera agotado al generar la imagen con sd-server (más de 120s)."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado en Gateway Image Handler: {str(e)}"
        )
