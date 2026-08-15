import os
import sys
import asyncio
import uvicorn
import ipaddress
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
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

# Helper de conexión a MongoDB (timeout de 1s para evitar esperas infinitas)
def get_db():
    user = os.getenv("MONGO_USER", "admin")
    password = os.getenv("MONGO_PASS", "joseMDB365$")
    host = os.getenv("MONGO_HOST", "127.0.0.1")
    db_name = os.getenv("MONGO_DB", "vllm")
    uri = f"mongodb://{user}:{password}@{host}:27017/{db_name}?authSource=admin"
    client = MongoClient(uri, serverSelectionTimeoutMS=1000)
    return client[db_name]

# Lógica de validación de tokens
def validate_token(token: str, service_name: str) -> bool:
    if token == MASTER_KEY:
        return True
        
    try:
        db = get_db()
        key_doc = db.api_keys.find_one({"key": token, "is_active": True})
        if not key_doc:
            return False
            
        # Validar permisos de servicio
        allowed_services = key_doc.get("services", [])
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
    except Exception as e:
        print(f"⚠️ Error al validar token en MongoDB: {e}", file=sys.stderr)
        return False

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
def create_proxy_app(service_name: str, target_port: int) -> FastAPI:
    app = FastAPI(title=f"Gateway Proxy para {service_name.upper()}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def proxy(request: Request, path: str):
        # 1. Validar reglas de IP antes de cualquier otra comprobación
        client_ip = request.client.host
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            
            # Comprobar Lista Negra (Blacklist)
            if any(client_ip_obj in net for net in cached_blacklist):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado: Dirección IP ({client_ip}) bloqueada por lista negra."
                )
                
            # Comprobar Lista Blanca (Whitelist)
            if cached_whitelist:
                if not any(client_ip_obj in net for net in cached_whitelist):
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
            
        # Obtener token de Bearer o parámetro query
        auth_header = request.headers.get("Authorization")
        token = ""
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
        else:
            token = request.query_params.get("api_key", "")
            
        if not token:
            # Registrar intento de autenticación fallido
            await register_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key faltante. Debe proporcionarse en la cabecera 'Authorization: Bearer <key>'"
            )
            
        # Validar token
        if not validate_token(token, service_name):
            # Registrar intento de autenticación fallido
            await register_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key inválida, desactivada, expirada o sin permisos para este servicio."
            )
            
        target_url = f"http://127.0.0.1:{target_port}/{path}"
        
        # Clonar cabeceras normalizando a minúsculas para evitar duplicados y colisiones de mayúsculas/minúsculas
        headers = {k.lower(): v for k, v in request.headers.items()}
        headers["host"] = f"127.0.0.1:{target_port}"
        headers["authorization"] = f"Bearer {MASTER_KEY}"
        
        # Quitar cabeceras de control hop-by-hop y de transferencia para evitar colisiones
        headers.pop("connection", None)
        headers.pop("keep-alive", None)
        headers.pop("transfer-encoding", None)
        headers.pop("upgrade", None)
        headers.pop("content-length", None) # Httpx lo recalcula si hay cuerpo
        
        body = await request.body()
        
        # Interceptar peticiones de chat para inyectar el prompt de sistema para razonamiento en gemma-4-reasoning
        if service_name == "gemma" and path.strip("/") == "v1/chat/completions" and request.method == "POST" and body:
            try:
                import json
                data = json.loads(body)
                
                # 1. Inyectar el system prompt de razonamiento para gemma-4-reasoning
                if data.get("model") == "gemma-4-reasoning" and "messages" in data:
                    messages = data["messages"]
                    # Buscar si hay un mensaje de sistema existente
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
                
                # 2. Forzar que vLLM no retorne la etiqueta <turn|> al final de la generación
                # agregándola al array 'stop' de la petición.
                stop_sequences = data.get("stop", [])
                if isinstance(stop_sequences, str):
                    stop_sequences = [stop_sequences]
                elif not isinstance(stop_sequences, list):
                    stop_sequences = []
                
                if "<turn|>" not in stop_sequences:
                    stop_sequences.append("<turn|>")
                    data["stop"] = stop_sequences
                
                # Volver a serializar el cuerpo modificado
                body = json.dumps(data).encode("utf-8")
            except Exception as json_err:
                print(f"⚠️ Error al interceptar y parsear JSON en el Gateway: {json_err}", file=sys.stderr, flush=True)

        client = get_http_client()
        
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
            
            # Limpiar cabeceras de respuesta conflictivas antes de enviar al cliente
            resp_headers = dict(resp.headers)
            resp_headers.pop("content-length", None)
            resp_headers.pop("transfer-encoding", None)
            resp_headers.pop("connection", None)
            
            # Generador asíncrono para streaming seguro.
            # El bloque finally asegura que el socket del backend se cierre al completarse
            # o si el cliente aborta la conexión a mitad de camino (evita fugas de descriptores de archivos).
            async def event_generator():
                buffer = b""
                try:
                    async for chunk in resp.aiter_raw():
                        buffer += chunk
                        if b"<turn|>" in buffer:
                            buffer = buffer.replace(b"<turn|>", b"")
                        if len(buffer) > 10:
                            yield buffer[:-10]
                            buffer = buffer[-10:]
                except asyncio.CancelledError:
                    print(f"🔌 Cliente cerró la conexión para {service_name} prematuramente.")
                finally:
                    if buffer:
                        if b"<turn|>" in buffer:
                            buffer = buffer.replace(b"<turn|>", b"")
                        yield buffer
                    await resp.aclose()
                    
            return StreamingResponse(
                event_generator(),
                status_code=resp.status_code,
                headers=resp_headers
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error al conectar con el motor de inferencia local ({service_name}): {str(e)}"
            )
            
    return app

async def run_servers():
    # Asegurar la creación del índice TTL sobre expires_at para autolimpiar los baneos de Fail2ban
    try:
        db = get_db()
        db.ip_rules.create_index("expires_at", expireAfterSeconds=0)
        print("💾 MongoDB: Índice TTL dinámico configurado o verificado en ip_rules.", flush=True)
    except Exception as e:
        print(f"⚠️ Error al inicializar índice TTL de IP en Gateway startup: {e}", file=sys.stderr, flush=True)

    gemma_port = int(os.getenv("GEMMA_BACKEND_PORT", "18000"))
    whisper_port = int(os.getenv("WHISPER_BACKEND_PORT", "18001"))
    tts_port = int(os.getenv("TTS_BACKEND_PORT", "18002"))
    diarization_port = int(os.getenv("DIARIZATION_BACKEND_PORT", "18003"))
    
    gemma_app = create_proxy_app("gemma", gemma_port)
    whisper_app = create_proxy_app("whisper", whisper_port)
    tts_app = create_proxy_app("tts", tts_port)
    diarization_app = create_proxy_app("diarization", diarization_port)
    
    # Configurar uvicorn para cada puerto público
    config_gemma = uvicorn.Config(gemma_app, host="0.0.0.0", port=8000, log_level="warning")
    config_whisper = uvicorn.Config(whisper_app, host="0.0.0.0", port=8001, log_level="warning")
    config_tts = uvicorn.Config(tts_app, host="0.0.0.0", port=8002, log_level="warning")
    config_diarization = uvicorn.Config(diarization_app, host="0.0.0.0", port=8003, log_level="warning")
    
    server_gemma = uvicorn.Server(config_gemma)
    server_whisper = uvicorn.Server(config_whisper)
    server_tts = uvicorn.Server(config_tts)
    server_diarization = uvicorn.Server(config_diarization)
    
    print("=" * 60)
    print("🛡️ Iniciando Gateway de Autenticación y Proxy...")
    print(f"🟢 Gemma Proxy:       8000 -> {gemma_port}")
    print(f"🟢 Whisper Proxy:     8001 -> {whisper_port}")
    print(f"🟢 F5-TTS Proxy:       8002 -> {tts_port}")
    print(f"🟢 Diarización Proxy: 8003 -> {diarization_port}")
    print("=" * 60)
    
    try:
        await asyncio.gather(
            sync_ip_rules_loop(),
            server_gemma.serve(),
            server_whisper.serve(),
            server_tts.serve(),
            server_diarization.serve()
        )
    finally:
        await close_http_client()

if __name__ == "__main__":
    try:
        asyncio.run(run_servers())
    except KeyboardInterrupt:
        print("\n👋 Gateway detenido por el usuario.")
