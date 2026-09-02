import os
import sys
import json
import time
import asyncio
from typing import Optional
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request, Response, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import API_KEY as MASTER_KEY
from gateway.core.ip_resolver import resolve_client_ip
from gateway.core.ip_rules import is_ip_allowed
from gateway.core.fail2ban import register_failed_attempt
from gateway.core.auth import extract_token, get_key_doc, validate_token_doc
from gateway.telemetry.usage_logger import save_usage_log
from gateway.telemetry.blocked_logger import save_blocked_request_log
from gateway.tools.web_search import handle_web_search, perform_ollama_web_search
from gateway.tools.pdf_generator import handle_pdf_generation, handle_pdf_download
from gateway.tools.doc_reader import handle_doc_reader
from gateway.tools.rag_endpoints import handle_rag_search, handle_rag_document, handle_rag_structure, handle_rag_library_index
from gateway.cloud.cloud_router import handle_models_list, resolve_cloud_model
from gateway.core.alignment_engine import enrich_chat_payload

# Cliente HTTP compartido globalmente para evitar fugas de sockets y memoria
_http_client = None


def get_http_client():
    global _http_client
    if _http_client is None:
        limits = httpx.Limits(max_connections=500, max_keepalive_connections=100)
        timeout = httpx.Timeout(10.0, connect=10.0, read=300.0, write=60.0)
        _http_client = httpx.AsyncClient(limits=limits, timeout=timeout)
    return _http_client


async def close_http_client():
    global _http_client
    if _http_client is not None:
        print("🛑 Cerrando pool de conexiones HTTP del Gateway...")
        await _http_client.aclose()
        _http_client = None


def create_proxy_app(service_name: str, target_port: int, fallback_port: Optional[int] = None) -> FastAPI:
    """
    Fábrica de aplicaciones proxy para cada puerto del Gateway.
    Integra seguridad, cuotas, interceptores de tools y enrutamiento inteligente.
    """
    app = FastAPI(title=f"Gateway Proxy - {service_name}", docs_url=None, redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Montar directorio de imágenes generadas para servicio de imagen o gemma
    images_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "outputs", "images")
    if os.path.exists(images_dir):
        app.mount("/outputs/images", StaticFiles(directory=images_dir), name="images")

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def proxy(request: Request, path: str, background_tasks: BackgroundTasks):
        if request.method == "OPTIONS":
            return Response(status_code=200)

        current_service = service_name
        current_target_port = target_port

        # 1. Validar reglas de IP antes de cualquier otra comprobación
        client_ip = resolve_client_ip(request)
        try:
            import ipaddress
            client_ip_obj = ipaddress.ip_address(client_ip)
            allowed, reason = is_ip_allowed(client_ip_obj)
            if not allowed:
                asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, f"ip_rule_blocked:{reason}"))
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado: {reason}"
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"⚠️ Error validando IP del cliente '{client_ip}': {e}", file=sys.stderr, flush=True)

        # 2. Descargas públicas de PDFs generados con TTL (variante 2 params: file_id/filename, variante 1 param: filename)
        if current_service == "gemma" and path.startswith("api/tools/pdf/download/") and request.method == "GET":
            parts = path.split("/")
            if len(parts) >= 6:
                file_id = parts[4]
                dl_filename = parts[5]
                return handle_pdf_download(file_id, dl_filename)
            elif len(parts) == 5:
                dl_filename = parts[4]
                return handle_pdf_download(file_id=dl_filename, dl_filename=dl_filename)

        # 3. Autenticación y Extracción de Tokens
        token = extract_token(request)

        if not token:
            await register_failed_attempt(client_ip)
            asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, "api_key"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key faltante. Debe proporcionarse en la cabecera 'Authorization: Bearer <key>' o 'X-Api-Key: <key>'."
            )

        # 4. Validar token y permisos de servicio
        key_doc = get_key_doc(token)
        if not validate_token_doc(key_doc, current_service):
            await register_failed_attempt(client_ip)
            asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, "api_key"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key inválida, desactivada, expirada o sin permisos para este servicio."
            )

        # 5. Validar cupo máximo de tokens
        if token != MASTER_KEY and key_doc:
            max_tokens = int(key_doc.get("max_tokens") or 0)
            used_tokens = int(key_doc.get("used_tokens") or 0)
            if max_tokens > 0 and used_tokens >= max_tokens:
                asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, f"token_quota_exceeded:{used_tokens}/{max_tokens}"))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Cupo de tokens agotado para esta clave API ({used_tokens:,} / {max_tokens:,} consumidos). Contacta al administrador para renovar o reiniciar tu cupo."
                )

        # 6. Interceptores de Tools Desacopladas (Gemma / Puerto 8000)
        if current_service == "gemma" and path.strip("/") in ["api/tools/web-search", "v1/tools/web_search", "v1/tools/web-search"] and request.method == "POST":
            return await handle_web_search(request)

        if current_service == "gemma" and path.strip("/") in ["api/tools/generate-pdf", "v1/tools/generate-pdf", "api/tools/pdf", "v1/tools/pdf"] and request.method == "POST":
            return await handle_pdf_generation(request, gateway_port=8000)

        if current_service == "gemma" and path.strip("/") in ["api/tools/read-file", "v1/tools/read_file", "v1/tools/read-file", "api/tools/extract-document", "api/tools/docling"] and request.method == "POST":
            return await handle_doc_reader(request)

        if current_service == "gemma" and path.strip("/") == "v1/models" and request.method == "GET":
            return await handle_models_list(token, key_doc, current_target_port)

        # Clonar y sanitizar cabeceras
        headers = {k.lower(): v for k, v in request.headers.items()}
        headers.pop("connection", None)
        headers.pop("keep-alive", None)
        headers.pop("transfer-encoding", None)
        headers.pop("upgrade", None)
        headers.pop("content-length", None)
        headers["accept-encoding"] = "identity"

        body = await request.body()
        start_time = datetime.now(timezone.utc).replace(tzinfo=None)

        model_name = current_service
        if current_service == "whisper":
            model_name = "openai/whisper-large-v3-turbo"
        elif current_service == "tts":
            model_name = "SWivid/F5-TTS"
        elif current_service == "diarization":
            model_name = "pyannote/speaker-diarization-3.1"
        elif current_service == "embeddings":
            model_name = "Qwen/Qwen3-Embedding-0.6B"

        # Interceptar /v1/embeddings en gemma proxy (puerto 8000)
        if current_service == "gemma" and path.strip("/") in ["v1/embeddings", "embeddings"] and request.method == "POST":
            is_master = (token == MASTER_KEY)
            allowed_services = key_doc.get("services", []) if key_doc else []
            if not is_master and ("embeddings" not in allowed_services):
                asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, "embeddings", path, "service_denied:embeddings"))
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tu clave API no tiene permisos autorizados para el servicio de Embeddings."
                )
            embeddings_backend_port = int(os.getenv("EMBEDDINGS_BACKEND_PORT", "18005"))
            current_target_port = embeddings_backend_port
            current_service = "embeddings"
            model_name = "Qwen/Qwen3-Embedding-0.6B"

        # Interceptar /v1/images/generations en gemma proxy (puerto 8000)
        if current_service == "gemma" and path.strip("/") in ["v1/images/generations", "images/generations"] and request.method == "POST":
            is_master = (token == MASTER_KEY)
            allowed_services = key_doc.get("services", []) if key_doc else []
            if not is_master and ("image" not in allowed_services):
                asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, "image", path, "service_denied:image"))
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tu clave API no tiene permisos autorizados para el servicio de Generación de Imágenes."
                )
            image_backend_port = int(os.getenv("IMAGE_BACKEND_PORT", "18004"))
            current_target_port = image_backend_port
            current_service = "image"
            model_name = os.getenv("IMAGE_MODEL", "stabilityai/sdxl-turbo")

        # Interceptar búsqueda RAG directa en LanceDB
        if path.strip("/") in ["v1/rag/search", "rag/search", "api/tools/rag-search"] and request.method == "POST":
            return await handle_rag_search(request, body)

        # Interceptar síntesis y lectura de documento RAG
        if path.strip("/") in ["v1/rag/document", "rag/document", "api/tools/rag-document", "api/tools/read-document"] and request.method == "POST":
            return await handle_rag_document(request, body)

        # Interceptar consulta de estructura y GPS Documental RAG
        if path.strip("/") in ["v1/rag/structure", "rag/structure", "api/tools/rag-structure", "api/tools/document-structure"] and request.method == "POST":
            return await handle_rag_structure(request, body)

        # Interceptar consulta de índice jerárquico macro de biblioteca RAG
        if path.strip("/") in ["v1/rag/library-index", "rag/library-index", "api/tools/rag-library-index", "api/tools/library-index"] and request.method in ["GET", "POST"]:
            return await handle_rag_library_index(request, body)

        # Resolución de modelos y enrutamiento inteligente (Cloud vs Local)
        is_cloud_request = False
        cloud_provider = None

        if current_service == "gemma" and body:
            try:
                data = json.loads(body)
                req_model = data.get("model", "")
                is_cloud_request, actual_model, cloud_provider, apply_rag_injection, base_vllm_model = await resolve_cloud_model(req_model, token, key_doc)

                if base_vllm_model:
                    data["model"] = base_vllm_model
                else:
                    data["model"] = actual_model

                model_name = actual_model or service_name

                # Delegar enriquecimiento de prompt, invariantes MEA, web search y RAG al submódulo especializado
                if path.strip("/") == "v1/chat/completions":
                    data = await enrich_chat_payload(
                        data=data,
                        actual_model=actual_model,
                        is_cloud_request=is_cloud_request,
                        apply_rag_injection=apply_rag_injection
                    )

                body = json.dumps(data).encode("utf-8")
            except Exception as json_err:
                print(f"⚠️ Error al interceptar y parsear JSON en el Gateway: {json_err}", file=sys.stderr, flush=True)

        if is_cloud_request and cloud_provider:
            base_url = cloud_provider['base_url'].rstrip("/")
            if base_url.endswith("/v1") and path.startswith("v1/"):
                target_url = f"{base_url[:-3]}/{path}"
            else:
                target_url = f"{base_url}/{path}"
            parsed_url = urlparse(cloud_provider['base_url'])
            headers["host"] = parsed_url.netloc
            headers["authorization"] = f"Bearer {cloud_provider['api_key']}"
        else:
            target_url = f"http://127.0.0.1:{current_target_port}/{path}"
            headers["host"] = f"127.0.0.1:{current_target_port}"
            headers["authorization"] = f"Bearer {MASTER_KEY}"

        client = get_http_client()
        resp = None

        try:
            try:
                req = client.build_request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    params=request.query_params
                )
                resp = await client.send(req, stream=True)

                if resp.status_code in (502, 503) and fallback_port and not is_cloud_request:
                    await resp.aclose()
                    resp = None
                    raise httpx.ConnectError(f"Backend principal retornó HTTP {resp.status_code if resp else 502}")
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException, httpx.ReadTimeout, httpx.NetworkError) as primary_err:
                if fallback_port and not is_cloud_request:
                    fallback_url = f"http://127.0.0.1:{fallback_port}/{path}"
                    fallback_headers = dict(headers)
                    fallback_headers["host"] = f"127.0.0.1:{fallback_port}"
                    print(f"⚠️ [Gateway Failover] Backend principal ({current_service} :{current_target_port}) no disponible ({primary_err}). Reenviando a Fallback CPU (:{fallback_port})...", flush=True)
                    req_fb = client.build_request(
                        method=request.method,
                        url=fallback_url,
                        headers=fallback_headers,
                        content=body,
                        params=request.query_params
                    )
                    resp = await client.send(req_fb, stream=True)
                else:
                    raise primary_err

            resp_headers = dict(resp.headers)
            resp_headers.pop("content-length", None)
            resp_headers.pop("transfer-encoding", None)
            resp_headers.pop("connection", None)
            resp_headers.pop("content-encoding", None)

            async def event_generator():
                buffer = b""
                total_bytes_yielded = 0
                accumulated_text = ""
                usage_data = None
                is_streaming = "text/event-stream" in resp_headers.get("content-type", "").lower()
                non_stream_body = b""

                try:
                    async for chunk in resp.aiter_bytes():
                        total_bytes_yielded += len(chunk)
                        if not is_streaming:
                            non_stream_body += chunk

                        if current_service == "gemma" and resp.status_code == 200 and is_streaming:
                            try:
                                chunk_str = chunk.decode("utf-8", errors="ignore")
                                for line in chunk_str.split("\n"):
                                    line = line.strip()
                                    if line.startswith("data: "):
                                        data_str = line[6:].strip()
                                        if data_str == "[DONE]":
                                            continue
                                        try:
                                            obj = json.loads(data_str)
                                            if "usage" in obj and obj["usage"]:
                                                usage_data = obj["usage"]
                                            if "choices" in obj and obj["choices"]:
                                                delta = obj["choices"][0].get("delta", {})
                                                content = delta.get("content", "")
                                                if content:
                                                    accumulated_text += content
                                        except Exception:
                                            pass
                            except Exception:
                                pass

                        buffer += chunk
                        if b"<turn|>" in buffer:
                            buffer = buffer.replace(b"<turn|>", b"")
                        if len(buffer) > 10:
                            yield buffer[:-10]
                            buffer = buffer[-10:]
                except asyncio.CancelledError:
                    print(f"🔌 Cliente cerró la conexión para {current_service} prematuramente.")
                finally:
                    if buffer:
                        if b"<turn|>" in buffer:
                            buffer = buffer.replace(b"<turn|>", b"")
                        total_bytes_yielded += len(buffer)
                        yield buffer
                    await resp.aclose()

                    if not is_streaming and non_stream_body and resp.status_code == 200:
                        try:
                            resp_json = json.loads(non_stream_body.decode("utf-8", errors="ignore"))
                            if "usage" in resp_json and resp_json["usage"]:
                                usage_data = resp_json["usage"]
                        except Exception as parse_err:
                            print(f"⚠️ Error parseando respuesta no-streaming: {parse_err}", file=sys.stderr, flush=True)

                    if resp.status_code == 200:
                        duration_sec = (datetime.now(timezone.utc).replace(tzinfo=None) - start_time).total_seconds()
                        prompt_tokens = 0
                        completion_tokens = 0
                        audio_duration_sec = 0.0

                        if current_service == "gemma":
                            if usage_data:
                                prompt_tokens = usage_data.get("prompt_tokens", 0)
                                completion_tokens = usage_data.get("completion_tokens", 0)
                            else:
                                completion_tokens = len(accumulated_text) // 4
                                try:
                                    req_data = json.loads(body)
                                    messages = req_data.get("messages", [])
                                    prompt_chars = sum(len(m.get("content", "")) for m in messages if isinstance(m, dict))
                                    prompt_tokens = prompt_chars // 4
                                    if prompt_chars > 0 and prompt_tokens == 0:
                                        prompt_tokens = 1
                                    if len(accumulated_text) > 0 and completion_tokens == 0:
                                        completion_tokens = 1
                                except Exception:
                                    pass
                        elif current_service == "tts":
                            if total_bytes_yielded > 44:
                                audio_duration_sec = (total_bytes_yielded - 44) / 48000.0
                        elif current_service in ("whisper", "diarization"):
                            if body:
                                audio_duration_sec = len(body) / 32000.0

                        background_tasks.add_task(
                            save_usage_log,
                            client_ip,
                            token,
                            current_service,
                            path,
                            model_name,
                            prompt_tokens,
                            completion_tokens,
                            audio_duration_sec,
                            duration_sec
                        )

            return StreamingResponse(
                event_generator(),
                status_code=resp.status_code,
                headers=resp_headers
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error al conectar con el motor de inferencia local ({current_service}): {str(e)}"
            )

    return app
