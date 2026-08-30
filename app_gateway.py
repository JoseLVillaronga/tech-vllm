import os
import sys
import re
import time
import asyncio
from typing import Optional
import uvicorn
import ipaddress
from fastapi import FastAPI, Request, Response, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import httpx
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Listas de subredes autorizadas/bloqueadas cargadas en caché en memoria RAM
cached_whitelist = []
cached_blacklist = []

# Control de intrusión (Fail2ban nativo)
failed_attempts = {}
failed_attempts_lock = asyncio.Lock()

# Modelos en la nube integrados (sincronizados periódicamente)
cached_cloud_models = {}         # Mapeo 'provider_slug/m_id' -> dict de información del proveedor
cached_cloud_models_by_raw = {}  # Mapeo 'm_id' -> lista de dicts de información de proveedores
cached_cloud_models_lock = asyncio.Lock()

def slugify_provider_name(name: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip().lower()).strip('_')
    return slug or "cloud"

# Clave API Maestra
MASTER_KEY = os.getenv("API_KEY", "token-abc123")

# Cliente HTTP compartido globalmente para evitar fugas de sockets y memoria
_http_client = None

def get_http_client():
    global _http_client
    if _http_client is None:
        # Configurar límites del pool de conexiones para evitar fugas
        limits = httpx.Limits(max_connections=500, max_keepalive_connections=100)
        # Timeout de 5 minutos para lectura de LLM con razonamiento largo
        timeout = httpx.Timeout(10.0, connect=10.0, read=300.0, write=60.0)
        _http_client = httpx.AsyncClient(limits=limits, timeout=timeout)
    return _http_client

async def close_http_client():
    global _http_client
    if _http_client is not None:
        print("🛑 Cerrando pool de conexiones HTTP del Gateway...")
        await _http_client.aclose()
        _http_client = None

# Helper para leer variables de entorno dinámicamente desde el sistema o archivo .env
def get_env_setting(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val is not None and val.strip() != "":
        return val.strip()
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == key:
                            clean_v = v.strip()
                            if (clean_v.startswith('"') and clean_v.endswith('"')) or (clean_v.startswith("'") and clean_v.endswith("'")):
                                clean_v = clean_v[1:-1]
                            return clean_v
    except Exception:
        pass
    return default

# Helper para ejecutar búsquedas en la web usando la API de Ollama Cloud
async def perform_ollama_web_search(query: str, max_results: int = 3) -> list:
    ollama_api_key = get_env_setting("OLLAMA_API_KEY", "").strip()
    search_enabled = get_env_setting("OLLAMA_SEARCH_ENABLED", "true").strip().lower() in ["true", "1", "yes"]
    
    if not search_enabled:
        print("⚠️ Ollama Web Search: Búsqueda web deshabilitada (OLLAMA_SEARCH_ENABLED=false)", file=sys.stderr, flush=True)
        return []
        
    if not ollama_api_key:
        print("⚠️ Ollama Web Search: OLLAMA_API_KEY no está configurada en .env", file=sys.stderr, flush=True)
        return []
        
    if not query or not query.strip():
        return []
        
    url = "https://ollama.com/api/web_search"
    headers = {
        "Authorization": f"Bearer {ollama_api_key}",
        "Content-Type": "application/json"
    }
    payload = {"query": query.strip()}
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                formatted = []
                for item in results[:max_results]:
                    title = item.get("title", "Sin título").strip()
                    item_url = item.get("url", "").strip()
                    content = item.get("content", "").strip()
                    if len(content) > 1500:
                        content = content[:1500] + "..."
                    formatted.append({
                        "title": title,
                        "url": item_url,
                        "content": content
                    })
                return formatted
            else:
                print(f"⚠️ Ollama Web Search API error: HTTP {resp.status_code} - {resp.text}", file=sys.stderr, flush=True)
                return []
    except Exception as e:
        print(f"⚠️ Error al consultar Ollama Web Search API: {e}", file=sys.stderr, flush=True)
        return []

# Helper de conexión a MongoDB (timeout de 1s para evitar esperas infinitas)
def get_db():
    user = os.getenv("MONGO_USER", "admin")
    password = os.getenv("MONGO_PASS", "joseMDB365$")
    host = os.getenv("MONGO_HOST", "127.0.0.1")
    db_name = os.getenv("MONGO_DB", "vllm")
    uri = f"mongodb://{user}:{password}@{host}:27017/{db_name}?authSource=admin"
    client = MongoClient(uri, serverSelectionTimeoutMS=1000)
    return client[db_name]

# Helper para obtener el documento de clave API y verificar reinicios periódicos de cupo
def get_key_doc(token: str):
    if token == MASTER_KEY:
        return {
            "name": "Master Key",
            "services": ["gemma", "whisper", "tts", "diarization", "embeddings", "image", "docling"],
            "allowed_providers": ["*"],
            "is_active": True
        }
    try:
        db = get_db()
        key_doc = db.api_keys.find_one({"key": token, "is_active": True})
        if not key_doc:
            return None
            
        # Evaluación de reinicio periódico de cupo de tokens (Diario / Mensual)
        quota_reset = key_doc.get("quota_reset", "none")
        if quota_reset in ["daily", "monthly"]:
            last_reset_at = key_doc.get("last_reset_at")
            now = datetime.utcnow()
            reset_needed = False
            
            if not last_reset_at:
                reset_needed = True
            else:
                if isinstance(last_reset_at, str):
                    try:
                        last_dt = datetime.fromisoformat(last_reset_at.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        last_dt = now
                elif isinstance(last_reset_at, datetime):
                    last_dt = last_reset_at.replace(tzinfo=None)
                else:
                    last_dt = now
                    
                if quota_reset == "daily":
                    if now.date() > last_dt.date():
                        reset_needed = True
                elif quota_reset == "monthly":
                    if (now.year, now.month) > (last_dt.year, last_dt.month):
                        reset_needed = True
                        
            if reset_needed:
                db.api_keys.update_one(
                    {"_id": key_doc["_id"]},
                    {"$set": {"used_tokens": 0, "last_reset_at": now}}
                )
                key_doc["used_tokens"] = 0
                key_doc["last_reset_at"] = now
                print(f"🔄 Gateway: Cupo de tokens reiniciado automáticamente ({quota_reset}) para la clave '{key_doc.get('name')}'", flush=True)
                
        return key_doc
    except Exception as e:
        print(f"⚠️ Error al consultar token en MongoDB: {e}", file=sys.stderr)
        return None

# Lógica de validación de tokens
def validate_token_doc(key_doc: dict, service_name: str) -> bool:
    if not key_doc:
        return False
    if key_doc.get("name") == "Master Key":
        return True
        
    # Validar permisos de servicio / proveedores
    allowed_services = key_doc.get("services", [])
    allowed_providers = key_doc.get("allowed_providers", [])
    
    if service_name == "gemma":
        # En el proxy gemma (puerto 8000), se permite el paso si tiene 'gemma' local o algún proveedor en la nube
        if "gemma" not in allowed_services and not allowed_providers:
            return False
    else:
        if service_name not in allowed_services:
            return False
        
    # Validar expiración
    expires_at = key_doc.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            # Soporte para fechas en formato ISO con o sin 'Z'
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            expires_dt = expires_at
            
        # Hacer comparación offset-aware si la fecha de expiración tiene zona horaria
        if expires_dt.tzinfo is not None:
            now = datetime.now(expires_dt.tzinfo)
        else:
            now = datetime.utcnow()
            
        if now > expires_dt:
            return False
            
    return True

def validate_token(token: str, service_name: str) -> bool:
    key_doc = get_key_doc(token)
    return validate_token_doc(key_doc, service_name)

# Función síncrona ejecutada en BackgroundTasks para no bloquear el bucle de eventos
def save_usage_log(ip: str, token: str, service: str, endpoint: str, model: str,
                   prompt_tokens: int, completion_tokens: int, audio_duration_sec: float,
                   duration_sec: float):
    try:
        db = get_db()
        # 1. Determinar el nombre de la API Key de forma segura
        if token == MASTER_KEY:
            key_name = "Master Key"
        else:
            key_doc = db.api_keys.find_one({"key": token})
            key_name = key_doc.get("name", "Clave Desconocida") if key_doc else "Clave Desconocida"
            
        # 2. Construir e insertar el log de auditoría
        total_tokens = (int(prompt_tokens) if prompt_tokens is not None else 0) + (int(completion_tokens) if completion_tokens is not None else 0)
        log_doc = {
            "timestamp": datetime.utcnow(),
            "ip": ip,
            "api_key_name": key_name,
            "service": service,
            "model": model or service,
            "endpoint": endpoint,
            "prompt_tokens": int(prompt_tokens) if prompt_tokens is not None else 0,
            "completion_tokens": int(completion_tokens) if completion_tokens is not None else 0,
            "audio_duration_sec": float(audio_duration_sec) if audio_duration_sec is not None else 0.0,
            "duration_sec": float(duration_sec) if duration_sec is not None else 0.0
        }
        db.usage_logs.insert_one(log_doc)
        
        # 3. Incrementar el contador atómico de tokens consumidos en la clave API de forma desacoplada
        if token != MASTER_KEY and total_tokens > 0:
            db.api_keys.update_one({"key": token}, {"$inc": {"used_tokens": total_tokens}})
            
        print(f"📊 Telemetría: Registro de uso guardado para '{service}' ({key_name}) - Modelo: {model} - Tokens: {total_tokens}", flush=True)
    except Exception as e:
        print(f"⚠️ Error al guardar telemetría de uso en MongoDB: {e}", file=sys.stderr, flush=True)

# Función síncrona para guardar bloqueos de seguridad en MongoDB en un hilo de fondo
def save_blocked_request_log(ip: str, service: str, endpoint: str, reason: str):
    try:
        db = get_db()
        log_doc = {
            "timestamp": datetime.utcnow(),
            "ip": ip,
            "service": service,
            "endpoint": endpoint or "/",
            "reason": reason
        }
        db.blocked_requests.insert_one(log_doc)
        print(f"🛡️ Seguridad: Intento de acceso bloqueado registrado para {ip} en servicio {service} ({reason})", flush=True)
    except Exception as e:
        print(f"⚠️ Error al guardar telemetría de seguridad en MongoDB: {e}", file=sys.stderr, flush=True)

# Lazo en segundo plano para sincronizar las reglas de IP desde MongoDB cada 10s
async def sync_ip_rules_loop():
    global cached_whitelist, cached_blacklist
    print("🛡️ Sincronizador de reglas de IP del Gateway Iniciado.", flush=True)
    while True:
        try:
            db = get_db()
            rules = list(db.ip_rules.find({"is_active": True}))
            
            new_whitelist = []
            new_blacklist = []
            
            for r in rules:
                network_str = r.get("network", "").strip()
                action = r.get("action", "").lower()
                if not network_str or not action:
                    continue
                try:
                    # Parsear rango/IP única como objeto de red IPv4Network/IPv6Network
                    net_obj = ipaddress.ip_network(network_str, strict=False)
                    if action == "whitelist":
                        new_whitelist.append(net_obj)
                    elif action == "blacklist":
                        new_blacklist.append(net_obj)
                except Exception as parse_err:
                    print(f"⚠️ Error parseando regla de IP '{network_str}': {parse_err}", file=sys.stderr, flush=True)
            
            cached_whitelist = new_whitelist
            cached_blacklist = new_blacklist
            
        except Exception as e:
            print(f"⚠️ Error al sincronizar reglas de IP: {e}", file=sys.stderr, flush=True)
            
        await asyncio.sleep(10)

async def sync_cloud_providers_loop():
    global cached_cloud_models, cached_cloud_models_by_raw
    print("☁️ Sincronizador de modelos externos en la nube del Gateway Iniciado.", flush=True)
    while True:
        try:
            db = get_db()
            providers = list(db.cloud_providers.find({"is_active": True}))
            
            new_cloud_models = {}
            new_cloud_models_by_raw = {}
            for p in providers:
                provider_id = str(p["_id"])
                name = p.get("name", "Desconocido")
                provider_slug = slugify_provider_name(name)
                base_url = p.get("base_url", "").rstrip("/")
                api_key = p.get("api_key", "")
                
                if not base_url or not api_key:
                    continue
                    
                try:
                    # Usar un cliente temporal rápido para no retrasar la sincronización de otros
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        headers = {"Authorization": f"Bearer {api_key}"}
                        resp = await client.get(f"{base_url}/models", headers=headers)
                        if resp.status_code == 200:
                            models_data = resp.json()
                            for m in models_data.get("data", []):
                                m_id = m.get("id")
                                if m_id:
                                    provider_info = {
                                        "provider_id": provider_id,
                                        "provider_name": name,
                                        "provider_slug": provider_slug,
                                        "raw_model_id": m_id,
                                        "base_url": base_url,
                                        "api_key": api_key
                                    }
                                    # Registro con prefijo único por proveedor (ej: 'openrouter/anthropic/claude-3.5-sonnet')
                                    prefixed_id = f"{provider_slug}/{m_id}"
                                    new_cloud_models[prefixed_id] = provider_info
                                    
                                    # Registro por nombre nativo (para resolución retrocompatible inteligente)
                                    if m_id not in new_cloud_models_by_raw:
                                        new_cloud_models_by_raw[m_id] = []
                                    new_cloud_models_by_raw[m_id].append(provider_info)
                except Exception as p_err:
                    print(f"⚠️ Gateway: Error obteniendo modelos del proveedor '{name}': {p_err}", file=sys.stderr, flush=True)
            
            async with cached_cloud_models_lock:
                cached_cloud_models = new_cloud_models
                cached_cloud_models_by_raw = new_cloud_models_by_raw
                
        except Exception as e:
            print(f"⚠️ Gateway: Error al sincronizar proveedores de la nube: {e}", file=sys.stderr, flush=True)
            
        await asyncio.sleep(60)

# Registrar un intento de autenticación fallido y banear la IP si llega a 3 fallos en 5m
async def register_failed_attempt(client_ip: str):
    global failed_attempts
    async with failed_attempts_lock:
        now = datetime.utcnow()
        attempts = failed_attempts.get(client_ip, [])
        # Filtrar fallos de hace más de 5 minutos (300s)
        attempts = [t for t in attempts if (now - t).total_seconds() < 300]
        attempts.append(now)
        failed_attempts[client_ip] = attempts
        
        if len(attempts) >= 3:
            try:
                db = get_db()
                network_cidr = f"{client_ip}/32"
                existing = db.ip_rules.find_one({"network": network_cidr})
                if not existing:
                    db.ip_rules.insert_one({
                        "name": f"Baneo Automático (Fallas API Key)",
                        "network": network_cidr,
                        "action": "blacklist",
                        "is_active": True,
                        "expires_at": now + timedelta(hours=48)
                    })
                    print(f"🚨 Fail2ban: IP {client_ip} bloqueada automáticamente por 48 horas tras 3 fallos en 5 minutos.", flush=True)
            except Exception as e:
                print(f"⚠️ Error en Fail2ban al registrar baneo para IP {client_ip}: {e}", file=sys.stderr, flush=True)
            # Limpiar los intentos de esta IP para resetear el contador una vez bloqueada
            failed_attempts.pop(client_ip, None)

# Creador de Apps Proxy
def create_proxy_app(service_name: str, target_port: int, fallback_port: Optional[int] = None) -> FastAPI:
    app = FastAPI(title=f"Gateway Proxy para {service_name.upper()}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Servir imágenes generadas como recursos estáticos
    out_img_dir = os.getenv("IMAGE_OUTPUT_DIR", "/home/jose/vllm/outputs/images")
    os.makedirs(out_img_dir, exist_ok=True)
    app.mount("/outputs/images", StaticFiles(directory=out_img_dir), name="images")
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def proxy(request: Request, path: str, background_tasks: BackgroundTasks):
        current_service = service_name
        current_target_port = target_port
        
        # 1. Validar reglas de IP antes de cualquier otra comprobación
        # Extraer IP real detrás de proxies (Caddy, Nginx, etc.)
        client_ip = request.headers.get("x-real-ip")
        if not client_ip:
            x_forwarded = request.headers.get("x-forwarded-for")
            if x_forwarded:
                client_ip = x_forwarded.split(",")[0].strip()
            else:
                client_ip = request.client.host
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            # Comprobar Lista Negra (Blacklist)
            if any(client_ip_obj in net for net in cached_blacklist):
                asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, "blacklist"))
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado: Dirección IP ({client_ip}) bloqueada por lista negra."
                )
                
            # Comprobar Lista Blanca (Whitelist)
            if cached_whitelist:
                if not any(client_ip_obj in net for net in cached_whitelist):
                    asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, "whitelist"))
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Acceso denegado: Dirección IP ({client_ip}) no autorizada en lista blanca."
                    )
        except HTTPException:
            raise
        except Exception as ip_err:
            print(f"⚠️ Error validando IP de cliente '{client_ip}': {ip_err}", file=sys.stderr)

        # Permitir peticiones preflight CORS libres
        if request.method == "OPTIONS":
            return Response(status_code=200)

        # Permitir descarga directa de PDFs generados vía GET
        if request.method == "GET" and ("api/tools/pdf/download/" in path or "v1/tools/pdf/download/" in path):
            try:
                from fastapi.responses import FileResponse
                
                parts = path.strip("/").split("/")
                file_id = ""
                dl_filename = "documento.pdf"
                for i, p in enumerate(parts):
                    if p == "download" and i + 1 < len(parts):
                        file_id = parts[i + 1]
                        if i + 2 < len(parts):
                            dl_filename = parts[i + 2]
                        break
                        
                if not file_id:
                    raise HTTPException(status_code=400, detail="ID de archivo no especificado.")
                    
                storage_dir = "/home/jose/vllm/outputs/pdfs"
                matched_file = None
                if os.path.exists(storage_dir):
                    for fname in os.listdir(storage_dir):
                        if fname.startswith(f"{file_id}_"):
                            matched_file = os.path.join(storage_dir, fname)
                            break
                        
                if not matched_file or not os.path.exists(matched_file):
                    raise HTTPException(status_code=404, detail="El documento PDF solicitado no existe o ha expirado.")
                    
                return FileResponse(
                    path=matched_file,
                    media_type="application/pdf",
                    filename=dl_filename,
                    headers={"Content-Disposition": f'attachment; filename="{dl_filename}"'}
                )
            except HTTPException:
                raise
            except Exception as dl_err:
                raise HTTPException(status_code=500, detail=f"Error al descargar PDF: {dl_err}")
            
        # Obtener token de cabeceras Authorization, X-Api-Key (Open-WebUI / Docling) o parámetro query
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
        auth_header = auth_header.strip()
        
        x_api_key = (
            request.headers.get("x-api-key")
            or request.headers.get("X-Api-Key")
            or request.headers.get("X-API-Key")
            or request.headers.get("X-API-KEY")
            or request.headers.get("api-key")
            or request.headers.get("apikey")
            or request.headers.get("x-auth-token")
            or ""
        ).strip()
        
        token = ""
        if auth_header:
            if auth_header.lower().startswith("bearer "):
                token = auth_header.split(" ", 1)[1].strip()
            elif auth_header.lower().startswith("api-key "):
                token = auth_header.split(" ", 1)[1].strip()
            else:
                token = auth_header
        elif x_api_key:
            token = x_api_key
        else:
            token = (
                request.query_params.get("api_key")
                or request.query_params.get("token")
                or request.query_params.get("key")
                or ""
            ).strip()
            
        if not token:
            # Registrar intento de autenticación fallido
            await register_failed_attempt(client_ip)
            asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, "api_key"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key faltante. Debe proporcionarse en la cabecera 'Authorization: Bearer <key>' o 'X-Api-Key: <key>'."
            )
            
        # Validar token
        key_doc = get_key_doc(token)
        if not validate_token_doc(key_doc, current_service):
            # Registrar intento de autenticación fallido
            await register_failed_attempt(client_ip)
            asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, "api_key"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key inválida, desactivada, expirada o sin permisos para este servicio."
            )
            
        # Validar cupo máximo de tokens
        if token != MASTER_KEY and key_doc:
            max_tokens = int(key_doc.get("max_tokens") or 0)
            used_tokens = int(key_doc.get("used_tokens") or 0)
            if max_tokens > 0 and used_tokens >= max_tokens:
                asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, f"token_quota_exceeded:{used_tokens}/{max_tokens}"))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Cupo de tokens agotado para esta clave API ({used_tokens:,} / {max_tokens:,} consumidos). Contacta al administrador para renovar o reiniciar tu cupo."
                )
            
        # Interceptar endpoint de Tool de Búsqueda Web (Ollama Cloud)
        if current_service == "gemma" and path.strip("/") in ["api/tools/web-search", "v1/tools/web_search", "v1/tools/web-search"] and request.method == "POST":
            try:
                import json
                tool_body = await request.body()
                tool_data = json.loads(tool_body) if tool_body else {}
                
                query = ""
                if "query" in tool_data:
                    query = tool_data["query"]
                elif "input" in tool_data:
                    query = tool_data["input"]
                elif "arguments" in tool_data and isinstance(tool_data["arguments"], dict):
                    query = tool_data["arguments"].get("query", "")
                elif "arguments" in tool_data and isinstance(tool_data["arguments"], str):
                    try:
                        arg_obj = json.loads(tool_data["arguments"])
                        query = arg_obj.get("query", "")
                    except Exception:
                        query = tool_data["arguments"]
                elif "messages" in tool_data:
                    user_msgs = [m.get("content", "") for m in tool_data["messages"] if m.get("role") == "user"]
                    if user_msgs:
                        query = user_msgs[-1]
                
                max_results = int(tool_data.get("max_results") or os.getenv("OLLAMA_SEARCH_MAX_RESULTS", "3"))
                
                search_results = await perform_ollama_web_search(query, max_results=max_results)
                
                formatted_snippets = []
                for idx, item in enumerate(search_results, 1):
                    formatted_snippets.append(
                        f"[{idx}] {item['title']}\n"
                        f"URL: {item['url']}\n"
                        f"Contenido: {item['content']}"
                    )
                formatted_text = "\n\n".join(formatted_snippets) if formatted_snippets else "No se encontraron resultados web para la consulta."
                
                response_payload = {
                    "success": True,
                    "query": query,
                    "count": len(search_results),
                    "results": search_results,
                    "formatted_context": formatted_text,
                    "text": formatted_text
                }
                
                return Response(
                    content=json.dumps(response_payload),
                    media_type="application/json",
                    status_code=200
                )
            except Exception as tool_err:
                print(f"⚠️ Error procesando tool de búsqueda web: {tool_err}", file=sys.stderr, flush=True)
                return Response(
                    content=json.dumps({"success": False, "error": str(tool_err)}),
                    media_type="application/json",
                    status_code=500
                )

        # Interceptar endpoint de Tool de Generación de PDF
        if current_service == "gemma" and path.strip("/") in ["api/tools/generate-pdf", "v1/tools/generate-pdf", "api/tools/pdf", "v1/tools/pdf"] and request.method == "POST":
            try:
                import json
                from pdf_engine import create_pdf_from_markdown
                
                tool_body = await request.body()
                tool_data = json.loads(tool_body) if tool_body else {}
                
                # Manejar inputs directos o empaquetados en 'arguments'
                if "arguments" in tool_data and isinstance(tool_data["arguments"], dict):
                    tool_data.update(tool_data["arguments"])
                elif "arguments" in tool_data and isinstance(tool_data["arguments"], str):
                    try:
                        arg_obj = json.loads(tool_data["arguments"])
                        if isinstance(arg_obj, dict):
                            tool_data.update(arg_obj)
                    except Exception:
                        pass
                
                title = tool_data.get("title") or tool_data.get("document_title") or "Documento Oficial"
                markdown_content = (
                    tool_data.get("markdown_content")
                    or tool_data.get("content")
                    or tool_data.get("text")
                    or tool_data.get("markdown")
                    or ""
                )
                filename = tool_data.get("filename") or tool_data.get("file_name") or None
                company_name = tool_data.get("company_name") or "Documento Oficial"
                
                if not markdown_content:
                    return Response(
                        content=json.dumps({"success": False, "error": "El parámetro 'markdown_content' no puede estar vacío."}),
                        media_type="application/json",
                        status_code=400
                    )
                
                # Construir base_url usando la cabecera Host de la petición entrante
                proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
                host_hdr = request.headers.get("host") or f"127.0.0.1:{GATEWAY_PORT}"
                base_url = f"{proto}://{host_hdr}"
                
                pdf_res = create_pdf_from_markdown(
                    title=title,
                    markdown_content=markdown_content,
                    filename=filename,
                    company_name=company_name,
                    base_url=base_url
                )
                
                return Response(
                    content=json.dumps(pdf_res),
                    media_type="application/json",
                    status_code=200
                )
            except Exception as pdf_err:
                print(f"⚠️ Error procesando tool de generación de PDF: {pdf_err}", file=sys.stderr, flush=True)
                return Response(
                    content=json.dumps({"success": False, "error": str(pdf_err)}),
                    media_type="application/json",
                    status_code=500
                )

        # Interceptar endpoint de Tool de Lectura y Análisis de Archivos/Documentos (Docling Server :5020)
        if current_service == "gemma" and path.strip("/") in ["api/tools/read-file", "v1/tools/read_file", "v1/tools/read-file", "api/tools/extract-document", "api/tools/docling"] and request.method == "POST":
            try:
                import json
                content_type = request.headers.get("content-type", "")
                docling_url = os.getenv("DOCLING_URL", "http://127.0.0.1:5020/v1/convert/file")
                extracted_md = ""
                filename = "documento"
                
                # Caso A: Subida directa de archivo (multipart/form-data)
                if "multipart/form-data" in content_type:
                    form = await request.form()
                    upload_file = form.get("file") or form.get("files") or form.get("document")
                    if upload_file:
                        filename = upload_file.filename or "documento"
                        file_bytes = await upload_file.read()
                        
                        files_payload = {"files": (filename, file_bytes, upload_file.content_type or "application/octet-stream")}
                        async with httpx.AsyncClient(timeout=45.0) as client:
                            d_resp = await client.post(docling_url, files=files_payload)
                            if d_resp.status_code == 200:
                                d_json = d_resp.json()
                                doc_obj = d_json.get("document", {})
                                if isinstance(doc_obj, dict):
                                    extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""
                            else:
                                return Response(
                                    content=json.dumps({"success": False, "error": f"Docling Serve respondió HTTP {d_resp.status_code}: {d_resp.text}"}),
                                    media_type="application/json",
                                    status_code=502
                                )
                # Caso B: JSON con 'file_path', 'url', 'base64'
                else:
                    tool_body = await request.body()
                    tool_data = json.loads(tool_body) if tool_body else {}
                    if "arguments" in tool_data and isinstance(tool_data["arguments"], dict):
                        tool_data.update(tool_data["arguments"])
                    elif "arguments" in tool_data and isinstance(tool_data["arguments"], str):
                        try:
                            arg_obj = json.loads(tool_data["arguments"])
                            if isinstance(arg_obj, dict):
                                tool_data.update(arg_obj)
                        except Exception:
                            pass
                    
                    file_path = tool_data.get("file_path") or tool_data.get("path")
                    file_url = tool_data.get("url")
                    base64_data = tool_data.get("base64")
                    filename = tool_data.get("filename") or "documento"
                    
                    if file_path and os.path.exists(file_path):
                        filename = os.path.basename(file_path)
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                        files_payload = {"files": (filename, file_bytes, "application/octet-stream")}
                        async with httpx.AsyncClient(timeout=45.0) as client:
                            d_resp = await client.post(docling_url, files=files_payload)
                            if d_resp.status_code == 200:
                                d_json = d_resp.json()
                                doc_obj = d_json.get("document", {})
                                if isinstance(doc_obj, dict):
                                    extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""
                    elif file_url:
                        async with httpx.AsyncClient(timeout=45.0) as client:
                            src_resp = await client.get(file_url)
                            if src_resp.status_code == 200:
                                filename = os.path.basename(file_url.split("?")[0]) or "documento.pdf"
                                files_payload = {"files": (filename, src_resp.content, "application/octet-stream")}
                                d_resp = await client.post(docling_url, files=files_payload)
                                if d_resp.status_code == 200:
                                    d_json = d_resp.json()
                                    doc_obj = d_json.get("document", {})
                                    if isinstance(doc_obj, dict):
                                        extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""
                    elif base64_data:
                        import base64
                        file_bytes = base64.b64decode(base64_data)
                        files_payload = {"files": (filename, file_bytes, "application/octet-stream")}
                        async with httpx.AsyncClient(timeout=45.0) as client:
                            d_resp = await client.post(docling_url, files=files_payload)
                            if d_resp.status_code == 200:
                                d_json = d_resp.json()
                                doc_obj = d_json.get("document", {})
                                if isinstance(doc_obj, dict):
                                    extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""

                if not extracted_md:
                    return Response(
                        content=json.dumps({"success": False, "error": "No se pudo extraer contenido del documento o el archivo está vacío."}),
                        media_type="application/json",
                        status_code=400
                    )

                response_payload = {
                    "success": True,
                    "filename": filename,
                    "length_chars": len(extracted_md),
                    "markdown_content": extracted_md,
                    "content": extracted_md
                }
                return Response(
                    content=json.dumps(response_payload),
                    media_type="application/json",
                    status_code=200
                )
            except Exception as e:
                print(f"⚠️ Error al procesar lectura de archivo en Gateway: {e}", file=sys.stderr, flush=True)
                return Response(
                    content=json.dumps({"success": False, "error": str(e)}),
                    media_type="application/json",
                    status_code=500
                )
            
        # Interceptar /v1/models en gemma proxy para combinar locales y en la nube según permisos granulares
        if current_service == "gemma" and path.strip("/") == "v1/models" and request.method == "GET":
            try:
                import json
                
                is_master = (token == MASTER_KEY)
                allowed_services = key_doc.get("services", []) if key_doc else []
                key_allowed_providers = key_doc.get("allowed_providers", []) if key_doc else []
                
                combined_models = []
                # 1. Modelos locales expuestos con prefijo 'local/'
                if is_master or ("gemma" in allowed_services):
                    try:
                        async with httpx.AsyncClient(timeout=3.0) as temp_cli:
                            headers_local = {"Authorization": f"Bearer {MASTER_KEY}"}
                            resp_local = await temp_cli.get(f"http://127.0.0.1:{current_target_port}/v1/models", headers=headers_local)
                            if resp_local.status_code == 200:
                                local_data = resp_local.json().get("data", [])
                                for lm in local_data:
                                    raw_id = lm.get("id", "")
                                    prefixed_id = f"local/{raw_id}" if not raw_id.startswith("local/") else raw_id
                                    combined_models.append({
                                        "id": prefixed_id,
                                        "object": "model",
                                        "created": lm.get("created", int(time.time())),
                                        "owned_by": "local"
                                    })
                                
                                # Si la búsqueda web está configurada, exponer también el modelo virtual local/gemma-4-web
                                ollama_api_key = get_env_setting("OLLAMA_API_KEY", "").strip()
                                ollama_search_on = get_env_setting("OLLAMA_SEARCH_ENABLED", "true").strip().lower() in ["true", "1", "yes"]
                                if ollama_search_on and ollama_api_key:
                                    combined_models.append({
                                        "id": "local/gemma-4-web",
                                        "object": "model",
                                        "created": int(time.time()),
                                        "owned_by": "local-web-search"
                                    })
                                
                                # Exponer modelo virtual local/gemma-4-rag (Base de Conocimiento LanceDB)
                                combined_models.append({
                                    "id": "local/gemma-4-rag",
                                    "object": "model",
                                    "created": int(time.time()),
                                    "owned_by": "local-rag-lancedb"
                                })
                                
                                # Exponer modelo virtual cloud-rag (Base de Conocimiento LanceDB + Proveedor en la Nube)
                                combined_models.append({
                                    "id": "cloud-rag",
                                    "object": "model",
                                    "created": int(time.time()),
                                    "owned_by": "cloud-rag-lancedb"
                                })
                                combined_models.append({
                                    "id": "local/cloud-rag",
                                    "object": "model",
                                    "created": int(time.time()),
                                    "owned_by": "cloud-rag-lancedb"
                                })
                                
                                # Si tiene permiso de embeddings, exponer también el modelo de embeddings
                                if is_master or ("embeddings" in allowed_services):
                                    combined_models.append({
                                        "id": "Qwen/Qwen3-Embedding-0.6B",
                                        "object": "model",
                                        "created": int(time.time()),
                                        "owned_by": "local-embeddings"
                                    })
                                    combined_models.append({
                                        "id": "text-embedding-3-small",
                                        "object": "model",
                                        "created": int(time.time()),
                                        "owned_by": "openai-alias"
                                    })
                                    
                                # Si tiene permiso de imagen, exponer también el modelo de generación de imágenes
                                if is_master or ("image" in allowed_services):
                                    img_model = get_env_setting("IMAGE_MODEL", "stabilityai/sdxl-turbo")
                                    combined_models.append({
                                        "id": img_model,
                                        "object": "model",
                                        "created": int(time.time()),
                                        "owned_by": "local-diffusion"
                                    })
                                    combined_models.append({
                                        "id": "local/image-generator",
                                        "object": "model",
                                        "created": int(time.time()),
                                        "owned_by": "local-diffusion"
                                    })
                    except Exception as le:
                        print(f"⚠️ Gateway: Error obteniendo modelos locales: {le}", file=sys.stderr, flush=True)
                
                # 2. Modelos de proveedores en la nube expuestos
                if is_master:
                    # Master Key ve todos los modelos de proveedores activos en caché
                    async with cached_cloud_models_lock:
                        for pref_id, p_info in cached_cloud_models.items():
                            prov_name = p_info.get("provider_name", "")
                            combined_models.append({
                                "id": pref_id,
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": prov_name
                            })
                elif key_doc:
                    # Clave secundaria: consultar modelos granulares autorizados en MongoDB
                    try:
                        db = get_db()
                        key_models = list(db.api_key_models.find({"key_id": key_doc["_id"]}))
                        if key_models:
                            for km in key_models:
                                pref_id = km.get("prefixed_id") or f"{km.get('provider_slug')}/{km.get('model_id')}"
                                prov_name = km.get("provider_name", "cloud")
                                combined_models.append({
                                    "id": pref_id,
                                    "object": "model",
                                    "created": int(time.time()),
                                    "owned_by": prov_name
                                })
                        else:
                            # Fallback retrocompatible para claves sin modelos granulares guardados
                            async with cached_cloud_models_lock:
                                for pref_id, p_info in cached_cloud_models.items():
                                    prov_id = p_info.get("provider_id", "")
                                    prov_name = p_info.get("provider_name", "")
                                    prov_slug = p_info.get("provider_slug", "")
                                    if ("*" in key_allowed_providers) or (prov_id in key_allowed_providers) or (prov_name in key_allowed_providers) or (prov_slug in key_allowed_providers):
                                        combined_models.append({
                                            "id": pref_id,
                                            "object": "model",
                                            "created": int(time.time()),
                                            "owned_by": prov_name
                                        })
                    except Exception as me:
                        print(f"⚠️ Gateway: Error obteniendo modelos cloud para clave: {me}", file=sys.stderr, flush=True)
                            
                return Response(
                    content=json.dumps({"object": "list", "data": combined_models}),
                    media_type="application/json",
                    status_code=200
                )
            except Exception as e:
                print(f"⚠️ Gateway: Error al combinar /v1/models: {e}", file=sys.stderr, flush=True)

        # Clonar cabeceras normalizando a minúsculas para evitar duplicados y colisiones de mayúsculas/minúsculas
        headers = {k.lower(): v for k, v in request.headers.items()}
        
        # Quitar cabeceras de control hop-by-hop y de transferencia para evitar colisiones
        headers.pop("connection", None)
        headers.pop("keep-alive", None)
        headers.pop("transfer-encoding", None)
        headers.pop("upgrade", None)
        headers.pop("content-length", None) # Httpx lo recalcula si hay cuerpo
        headers["accept-encoding"] = "identity" # Solicitar texto plano sin compresión (evita streams binarios gzip/br)
        
        body = await request.body()
        
        # Inicializar variables de telemetría
        start_time = datetime.utcnow()
        model_name = current_service
        if current_service == "whisper":
            model_name = "openai/whisper-large-v3-turbo"
        elif current_service == "tts":
            model_name = "SWivid/F5-TTS"
        elif current_service == "diarization":
            model_name = "pyannote/speaker-diarization-3.1"
        elif current_service == "embeddings":
            model_name = "Qwen/Qwen3-Embedding-0.6B"
            
        # Interceptar /v1/embeddings en gemma proxy (puerto 8000) para enrutar a Qwen3-Embedding en RAM
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

        # Interceptar /v1/images/generations en gemma proxy (puerto 8000) para enrutar al generador de imágenes
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

        # Interceptar /v1/rag/search o /api/tools/rag-search para búsqueda directa en LanceDB
        if path.strip("/") in ["v1/rag/search", "rag/search", "api/tools/rag-search"] and request.method == "POST":
            try:
                import json
                from rag_engine import search_knowledge_base, format_rag_context_for_llm, get_rag_settings
                
                rag_sett = get_rag_settings()
                if not rag_sett.get("enabled", True):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="El servicio de Base de Conocimiento RAG está desactivado globalmente en la suite."
                    )
                
                body_data = json.loads(body) if body else {}
                query = body_data.get("query", "").strip()
                tema = body_data.get("tema") or None
                temas = body_data.get("temas") or None
                top_k = int(body_data.get("top_k", 5))
                
                if not query:
                    raise HTTPException(status_code=400, detail="El parámetro 'query' no puede estar vacío.")
                    
                t_rag_0 = time.time()
                results = search_knowledge_base(query=query, tema=tema, temas=temas, top_k=top_k)
                dur_rag_ms = round((time.time() - t_rag_0) * 1000, 2)
                context_str = format_rag_context_for_llm(results)
                
                return JSONResponse(content={
                    "query": query,
                    "tema": tema,
                    "temas": temas,
                    "results_count": len(results),
                    "latency_ms": dur_rag_ms,
                    "context": context_str,
                    "results": results
                })
            except HTTPException:
                raise
            except Exception as re:
                raise HTTPException(status_code=500, detail=f"Error en búsqueda RAG: {str(re)}")

        # Interceptar /v1/rag/document o /api/tools/rag-document para síntesis y lectura de documento completo
        if path.strip("/") in ["v1/rag/document", "rag/document", "api/tools/rag-document", "api/tools/read-document"] and request.method == "POST":
            try:
                import json
                from rag_engine import get_document_full_content, get_rag_settings
                
                rag_sett = get_rag_settings()
                if not rag_sett.get("enabled", True):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="El servicio de Base de Conocimiento RAG está desactivado globalmente en la suite."
                    )
                
                body_data = json.loads(body) if body else {}
                doc_id = body_data.get("doc_id", "").strip()
                parte = int(body_data.get("parte", 1))
                token_threshold = int(body_data.get("token_threshold", 60000))
                chunk_threshold = body_data.get("chunk_threshold")
                chunk_threshold_val = int(chunk_threshold) if chunk_threshold is not None else None
                
                if not doc_id:
                    raise HTTPException(status_code=400, detail="El parámetro 'doc_id' es obligatorio para leer el documento.")
                    
                t_doc_0 = time.time()
                res = get_document_full_content(
                    doc_id=doc_id,
                    parte=parte,
                    token_threshold=token_threshold,
                    chunk_threshold=chunk_threshold_val
                )
                dur_doc_ms = round((time.time() - t_doc_0) * 1000, 2)
                
                if not res.get("success", False):
                    raise HTTPException(status_code=404, detail=res.get("error", "Error recuperando documento."))
                    
                return JSONResponse(content={
                    "success": True,
                    "doc_id": res.get("doc_id"),
                    "titulo": res.get("titulo"),
                    "tema": res.get("tema"),
                    "autor": res.get("autor"),
                    "total_chunks": res.get("total_chunks"),
                    "total_doc_tokens": res.get("total_doc_tokens"),
                    "tokens_en_esta_parte": res.get("tokens_en_esta_parte"),
                    "modo": res.get("modo"),
                    "parte_actual": res.get("parte_actual", 1),
                    "total_partes": res.get("total_partes", 1),
                    "chunks_en_esta_parte": res.get("chunks_en_esta_parte", res.get("total_chunks")),
                    "latency_ms": dur_doc_ms,
                    "content": res.get("content", "")
                })
            except HTTPException:
                raise
            except Exception as de:
                raise HTTPException(status_code=500, detail=f"Error en lectura de documento RAG: {str(de)}")

        # Determinar si es una petición a un modelo en la nube o local
        is_cloud_request = False
        cloud_provider = None
        matched_cloud = False
        
        if current_service == "gemma" and body:
            try:
                import json
                data = json.loads(body)
                req_model = data.get("model", "")
                
                is_master = (token == MASTER_KEY)
                allowed_services = key_doc.get("services", []) if key_doc else []
                key_allowed_providers = key_doc.get("allowed_providers", []) if key_doc else []
                
                actual_model = req_model
                apply_rag_injection = False
                
                if req_model in ["local/gemma-4-web", "gemma-4-web"]:
                    # Caso Especial: Modelo virtual con Búsqueda Web Integrada
                    is_cloud_request = False
                    actual_model = "gemma-4-web"
                    base_vllm_model = os.getenv("MODEL", "google/gemma-4-E4B-it").strip('"').strip("'")
                    data["model"] = base_vllm_model
                elif req_model in ["local/gemma-4-rag", "gemma-4-rag"]:
                    # Caso Especial: Modelo virtual con Base de Conocimiento RAG LanceDB Integrada
                    is_cloud_request = False
                    actual_model = "gemma-4-rag"
                    apply_rag_injection = True
                    base_vllm_model = os.getenv("MODEL", "google/gemma-4-E4B-it").strip('"').strip("'")
                    data["model"] = base_vllm_model
                elif req_model in ["cloud-rag", "local/cloud-rag", "cloud/rag"]:
                    # Caso Especial: Alias virtual Cloud RAG (LanceDB + Proveedor en la Nube)
                    from rag_engine import get_rag_settings
                    rag_sett = get_rag_settings()
                    c_prov_id = rag_sett.get("cloud_rag_provider_id")
                    c_model_id = rag_sett.get("cloud_rag_model_id")
                    
                    db = get_db()
                    prov_obj = None
                    if c_prov_id:
                        try:
                            from bson import ObjectId
                            prov_obj = db.cloud_providers.find_one({"_id": ObjectId(c_prov_id), "is_active": True})
                        except Exception:
                            prov_obj = db.cloud_providers.find_one({"_id": c_prov_id, "is_active": True})
                    
                    if not prov_obj:
                        prov_obj = db.cloud_providers.find_one({"is_active": True})
                        
                    if not prov_obj:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No hay ningún proveedor en la nube configurado o activo en la suite para 'cloud-rag'. Configúralo en la pestaña Base RAG del Dashboard."
                        )
                        
                    p_slug = slugify_provider_name(prov_obj.get("name", "cloud"))
                    target_cloud_model = c_model_id or "default"
                    
                    is_cloud_request = True
                    cloud_provider = {
                        "provider_id": str(prov_obj["_id"]),
                        "provider_name": prov_obj.get("name", ""),
                        "provider_slug": p_slug,
                        "base_url": prov_obj.get("base_url", ""),
                        "api_key": prov_obj.get("api_key", ""),
                        "raw_model_id": target_cloud_model
                    }
                    actual_model = target_cloud_model
                    data["model"] = actual_model
                    apply_rag_injection = True
                elif req_model.startswith("local/"):
                    # Caso 1: Modelo local con prefijo explícito 'local/'
                    is_cloud_request = False
                    actual_model = req_model[6:] # Despojar 'local/'
                    data["model"] = actual_model
                else:
                    clean_req_model = req_model
                    if req_model.endswith("-rag") and req_model not in ["gemma-4-rag", "cloud-rag"]:
                        clean_req_model = req_model[:-4]
                        apply_rag_injection = True
                    elif req_model.endswith(":rag"):
                        clean_req_model = req_model[:-4]
                        apply_rag_injection = True
                        
                    matched_cloud = False
                    if not is_master and key_doc:
                        # 1. Consultar modelos granulares autorizados en MongoDB para esta clave
                        try:
                            db = get_db()
                            matched_km = db.api_key_models.find_one({
                                "key_id": key_doc["_id"],
                                "$or": [
                                    {"prefixed_id": clean_req_model},
                                    {"model_id": clean_req_model}
                                ]
                            })
                            if matched_km:
                                p_id = matched_km.get("provider_id")
                                prov_obj = db.cloud_providers.find_one({"_id": p_id, "is_active": True})
                                if prov_obj:
                                    is_cloud_request = True
                                    cloud_provider = {
                                        "provider_id": str(prov_obj["_id"]),
                                        "provider_name": prov_obj.get("name", ""),
                                        "provider_slug": matched_km.get("provider_slug") or slugify_provider_name(prov_obj.get("name", "")),
                                        "base_url": prov_obj.get("base_url", ""),
                                        "api_key": prov_obj.get("api_key", ""),
                                        "raw_model_id": matched_km.get("model_id", clean_req_model)
                                    }
                                    actual_model = matched_km.get("model_id", clean_req_model)
                                    data["model"] = actual_model
                                    matched_cloud = True
                        except Exception as m_err:
                            print(f"⚠️ Gateway: Error validando modelo en MongoDB: {m_err}", file=sys.stderr, flush=True)
                    
                    if not matched_cloud:
                        async with cached_cloud_models_lock:
                            if clean_req_model in cached_cloud_models:
                                # Caso 2: Modelo en la nube con prefijo de proveedor exacto (ej: 'openrouter/anthropic/claude-3.5-sonnet')
                                is_cloud_request = True
                                cloud_provider = cached_cloud_models[clean_req_model]
                                actual_model = cloud_provider.get("raw_model_id", clean_req_model)
                                data["model"] = actual_model # Despojar prefijo de proveedor antes de enviar a la nube
                            elif clean_req_model in cached_cloud_models_by_raw:
                                # Caso 3: Modelo enviado por nombre nativo (sin prefijo).
                                candidate_providers = cached_cloud_models_by_raw[clean_req_model]
                                authorized_candidate = None
                                for cp in candidate_providers:
                                    p_id = cp.get("provider_id", "")
                                    p_name = cp.get("provider_name", "")
                                    p_slug = cp.get("provider_slug", "")
                                    if is_master or ("*" in key_allowed_providers) or (p_id in key_allowed_providers) or (p_name in key_allowed_providers) or (p_slug in key_allowed_providers):
                                        authorized_candidate = cp
                                        break
                                
                                if ("gemma" in allowed_services or is_master) and (clean_req_model in ["gemma-4-reasoning", "gemma-4-web", "gemma-4-rag", "google/gemma-4-E4B-it"] or not authorized_candidate):
                                    is_cloud_request = False
                                    actual_model = clean_req_model
                                    if clean_req_model in ["gemma-4-web", "gemma-4-rag"]:
                                        data["model"] = os.getenv("MODEL", "google/gemma-4-E4B-it").strip('"').strip("'")
                                elif authorized_candidate:
                                    is_cloud_request = True
                                    cloud_provider = authorized_candidate
                                    actual_model = clean_req_model
                                    data["model"] = actual_model
                                else:
                                    is_cloud_request = True
                                    cloud_provider = candidate_providers[0]
                                    actual_model = clean_req_model
                            else:
                                is_cloud_request = False
                                actual_model = clean_req_model

                model_name = actual_model or service_name
                
                # Inyectar fecha y hora actual en el system prompt para todos los modelos (locales y en la nube)
                if path.strip("/") == "v1/chat/completions" and "messages" in data:
                    messages = data["messages"]
                    now_local = datetime.now()
                    dias_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                    meses_ano = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
                    dia_nombre = dias_semana[now_local.weekday()]
                    mes_nombre = meses_ano[now_local.month - 1]
                    fecha_hora_str = f"Fecha y hora actual: {dia_nombre} {now_local.day} de {mes_nombre} de {now_local.year}, {now_local.strftime('%H:%M:%S')} (Hora local)."
                    
                    system_msg = next((m for m in messages if m.get("role") == "system"), None)
                    if system_msg:
                        orig_system = system_msg.get("content", "")
                        if "Fecha y hora actual:" not in orig_system:
                            system_msg["content"] = f"{fecha_hora_str}\n\n{orig_system}".strip()
                    else:
                        messages.insert(0, {"role": "system", "content": fecha_hora_str})

                # Inyectar el system prompt de razonamiento para gemma-4-reasoning si es local
                if not is_cloud_request and actual_model == "gemma-4-reasoning" and path.strip("/") == "v1/chat/completions" and "messages" in data:
                    messages = data["messages"]
                    system_msg = next((m for m in messages if m.get("role") == "system"), None)
                    reasoning_instruction = (
                        "Eres un modelo de razonamiento. Debes escribir tu proceso de pensamiento "
                        "paso a paso envuelto dentro de etiquetas <think>...</think>, y luego "
                        "escribir tu respuesta final."
                    )
                    if system_msg:
                        original_content = system_msg.get("content", "")
                        if reasoning_instruction not in original_content:
                            system_msg["content"] = f"{original_content}\n\n{reasoning_instruction}".strip()
                    else:
                        messages.insert(0, {"role": "system", "content": reasoning_instruction})
                        
                # Inyectar contexto de búsqueda web en tiempo real para el modelo virtual gemma-4-web
                if not is_cloud_request and actual_model == "gemma-4-web" and path.strip("/") == "v1/chat/completions" and "messages" in data:
                    messages = data["messages"]
                    last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
                    user_query = ""
                    if last_user_msg:
                        content_val = last_user_msg.get("content", "")
                        if isinstance(content_val, str):
                            user_query = content_val
                        elif isinstance(content_val, list):
                            text_parts = [p.get("text", "") for p in content_val if isinstance(p, dict) and p.get("type") == "text"]
                            user_query = " ".join(text_parts)
                    
                    if user_query:
                        max_res = int(get_env_setting("OLLAMA_SEARCH_MAX_RESULTS", "3"))
                        web_results = await perform_ollama_web_search(user_query, max_results=max_res)
                        if web_results:
                            snippets = []
                            for idx, r in enumerate(web_results, 1):
                                snippets.append(
                                    f"[{idx}] {r['title']}\n"
                                    f"URL: {r['url']}\n"
                                    f"Contenido: {r['content']}"
                                )
                            web_context = "\n\n".join(snippets)
                            search_prompt = (
                                f"\n\n[INFORMACIÓN DE BÚSQUEDA WEB EN TIEMPO REAL (VÍA OLLAMA)]:\n"
                                f"{web_context}\n"
                                f"--------------------------------------------------\n"
                                f"Instrucciones: Utiliza la información web anterior para responder de forma precisa, "
                                f"actualizada y cita las fuentes o enlaces si es relevante."
                            )
                            
                            system_msg = next((m for m in messages if m.get("role") == "system"), None)
                            if system_msg:
                                system_msg["content"] = f"{system_msg.get('content', '')}{search_prompt}".strip()
                            else:
                                messages.insert(0, {"role": "system", "content": search_prompt.strip()})
                
                # Inyectar contexto de Base de Conocimiento RAG (LanceDB) para modelos con RAG (gemma-4-rag, cloud-rag o sufijo -rag)
                if (apply_rag_injection or actual_model == "gemma-4-rag") and path.strip("/") == "v1/chat/completions" and "messages" in data:
                    try:
                        from rag_engine import search_knowledge_base, format_rag_context_for_llm, get_rag_settings
                        rag_sett = get_rag_settings()
                        if rag_sett.get("enabled", True):
                            messages = data["messages"]
                            last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
                            user_query = ""
                            if last_user_msg:
                                content_val = last_user_msg.get("content", "")
                                if isinstance(content_val, str):
                                    user_query = content_val
                                elif isinstance(content_val, list):
                                    text_parts = [p.get("text", "") for p in content_val if isinstance(p, dict) and p.get("type") == "text"]
                                    user_query = " ".join(text_parts)
                                    
                            if user_query:
                                rag_results = search_knowledge_base(query=user_query, top_k=4)
                                if rag_results:
                                    rag_context_str = format_rag_context_for_llm(rag_results)
                                    rag_prompt = (
                                        f"\n\n[CONTEXTO DE LA BASE DE CONOCIMIENTO DOCUMENTAL (LANCEDB - TECCAM)]:\n"
                                        f"{rag_context_str}\n"
                                        f"--------------------------------------------------\n"
                                        f"Instrucciones: Responde a la pregunta del usuario utilizando de manera prioritaria y rigurosa la información y fuentes proporcionadas arriba. Cita los documentos y secciones de donde proviene la información cuando sea relevante."
                                    )
                                    system_msg = next((m for m in messages if m.get("role") == "system"), None)
                                    if system_msg:
                                        system_msg["content"] = f"{system_msg.get('content', '')}{rag_prompt}".strip()
                                    else:
                                        messages.insert(0, {"role": "system", "content": rag_prompt.strip()})
                    except Exception as re:
                        print(f"⚠️ Error en contextualización RAG: {re}", file=sys.stderr, flush=True)

                body = json.dumps(data).encode("utf-8")
            except Exception as json_err:
                print(f"⚠️ Error al interceptar y parsear JSON en el Gateway: {json_err}", file=sys.stderr, flush=True)

        # Validación granular de permisos por modelo/proveedor en el servicio Gemma
        if current_service == "gemma":
            is_master = (token == MASTER_KEY)
            if is_cloud_request and cloud_provider:
                provider_id = cloud_provider.get("provider_id", "")
                provider_name = cloud_provider.get("provider_name", "")
                provider_slug = cloud_provider.get("provider_slug", "")
                key_allowed_providers = key_doc.get("allowed_providers", []) if key_doc else []
                is_authorized = (
                    is_master
                    or ("*" in key_allowed_providers)
                    or (provider_id in key_allowed_providers)
                    or (provider_name in key_allowed_providers)
                    or (provider_slug in key_allowed_providers)
                    or matched_cloud
                )
                if not is_authorized:
                    asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, f"cloud_provider_denied:{provider_name}"))
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Acceso denegado: Esta clave API no tiene permisos para acceder al proveedor en la nube '{provider_name}'."
                    )
            elif not is_cloud_request and path.strip("/") != "v1/models":
                allowed_services = key_doc.get("services", []) if key_doc else []
                if not is_master and ("gemma" not in allowed_services):
                    asyncio.create_task(asyncio.to_thread(save_blocked_request_log, client_ip, current_service, path, "local_gemma_denied"))
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acceso denegado: Esta clave API no tiene permisos para acceder al modelo local Gemma."
                    )

        if is_cloud_request:
            base_url = cloud_provider['base_url'].rstrip("/")
            if base_url.endswith("/v1") and path.startswith("v1/"):
                target_url = f"{base_url[:-3]}/{path}"
            else:
                target_url = f"{base_url}/{path}"
            from urllib.parse import urlparse
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
            # 1. Intentar enviar petición al backend principal
            try:
                # Construir petición proxy
                req = client.build_request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    params=request.query_params
                )
                
                # Enviar petición y recibir cabeceras por streaming
                resp = await client.send(req, stream=True)
                
                # Si el backend principal devuelve 502/503 y tenemos fallback_port configurado, conmutar
                if resp.status_code in (502, 503) and fallback_port and not is_cloud_request:
                    await resp.aclose()
                    resp = None
                    raise httpx.ConnectError(f"Backend principal retornó HTTP {resp.status_code if resp else 502}")
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException, httpx.ReadTimeout, httpx.NetworkError) as primary_err:
                if fallback_port and not is_cloud_request:
                    fallback_url = f"http://127.0.0.1:{fallback_port}/{path}"
                    fallback_headers = dict(headers)
                    fallback_headers["host"] = f"127.0.0.1:{fallback_port}"
                    print(f"⚠️ [Gateway Failover] Backend principal ({current_service} :{current_target_port}) no disponible ({primary_err}). Reenviando transparentemente a Fallback CPU (:{fallback_port})...", flush=True)
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
            
            # Limpiar cabeceras de respuesta conflictivas antes de enviar al cliente
            resp_headers = dict(resp.headers)
            resp_headers.pop("content-length", None)
            resp_headers.pop("transfer-encoding", None)
            resp_headers.pop("connection", None)
            resp_headers.pop("content-encoding", None)
            
            # Generador asíncrono para streaming seguro.
            # El bloque finally asegura que el socket del backend se cierre al completarse
            # o si el cliente aborta la conexión a mitad de camino (evita fugas de descriptores de archivos).
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
                        
                        # Extraer tokens del stream en caliente si es Gemma y la petición fue exitosa
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
                                            import json
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
                    
                    # Extraer tokens de respuestas no-streaming
                    if not is_streaming and non_stream_body and resp.status_code == 200:
                        try:
                            import json
                            resp_json = json.loads(non_stream_body.decode("utf-8", errors="ignore"))
                            if "usage" in resp_json and resp_json["usage"]:
                                usage_data = resp_json["usage"]
                        except Exception as parse_err:
                            print(f"⚠️ Error al parsear JSON de respuesta no-streaming: {parse_err}", file=sys.stderr, flush=True)
                    # Registrar telemetría al finalizar el stream si el status fue 200 OK
                    if resp.status_code == 200:
                        duration_sec = (datetime.utcnow() - start_time).total_seconds()
                        prompt_tokens = 0
                        completion_tokens = 0
                        audio_duration_sec = 0.0
                        
                        if current_service == "gemma":
                            if usage_data:
                                prompt_tokens = usage_data.get("prompt_tokens", 0)
                                completion_tokens = usage_data.get("completion_tokens", 0)
                            else:
                                # Estimación en caso de que no venga el campo usage
                                completion_tokens = len(accumulated_text) // 4
                                try:
                                    import json
                                    req_data = json.loads(body)
                                    messages = req_data.get("messages", [])
                                    prompt_chars = sum(len(m.get("content", "")) for m in messages if isinstance(m, dict))
                                    prompt_tokens = prompt_chars // 4
                                    # Asegurar mínimo de 1 token si hay contenido
                                    if prompt_chars > 0 and prompt_tokens == 0:
                                        prompt_tokens = 1
                                    if len(accumulated_text) > 0 and completion_tokens == 0:
                                        completion_tokens = 1
                                except Exception:
                                    pass
                        elif current_service == "tts":
                            # PCM 24kHz Mono = 48,000 bytes por segundo de audio (descontando cabecera de 44 bytes)
                            if total_bytes_yielded > 44:
                                audio_duration_sec = (total_bytes_yielded - 44) / 48000.0
                        elif current_service in ("whisper", "diarization"):
                            # Estimación sobre el cuerpo del archivo (WAV 16kHz mono = 32,000 bytes/segundo)
                            if body:
                                audio_duration_sec = len(body) / 32000.0
                                
                        # Agendar la escritura en MongoDB de forma asíncrona y no bloqueante
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

async def run_servers():
    # Asegurar la creación del índice TTL sobre expires_at para autolimpiar los baneos de Fail2ban
    try:
        db = get_db()
        db.ip_rules.create_index("expires_at", expireAfterSeconds=0)
        # Asegurar la creación del índice TTL de 6 meses en la colección usage_logs (15,552,000 segundos)
        db.usage_logs.create_index("timestamp", expireAfterSeconds=15552000)
        # Asegurar la creación del índice TTL de 6 meses en la colección blocked_requests (15,552,000 segundos)
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
    
    # Configurar uvicorn para cada puerto público
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
    print("🛡️ Iniciando Gateway de Autenticación y Proxy...")
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

if __name__ == "__main__":
    try:
        asyncio.run(run_servers())
    except KeyboardInterrupt:
        print("\n👋 Gateway detenido por el usuario.")
