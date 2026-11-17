import os
import sys
import ipaddress
from fastapi import Request

# --- Resolución segura de la IP real del cliente (anti-suplantación por cabeceras) ---
# Proxies de confianza (IP o CIDR, separados por coma). La IP resuelta desde
# X-Real-Ip / X-Forwarded-For SOLO se acepta cuando la conexión directa (socket,
# no falseable) proviene de uno de estos rangos. Así se evita que un cliente
# externo falsee su IP y tanto eludir listas IP como envenenar el Fail2ban interno.
TRUSTED_PROXIES = []
_TRUSTED_PROXIES_RAW = os.getenv("TRUSTED_PROXIES", "").strip()
# Default seguro: solo proxies locales (loopback). Si hay un proxy real delante
# (p. ej. Caddy/Nginx en 192.168.1.10), añádelo aquí para preservar la IP del cliente.
_DEFAULT_TRUSTED = "127.0.0.0/8,::1/128"
for _c in (_TRUSTED_PROXIES_RAW or _DEFAULT_TRUSTED).split(","):
    _c = _c.strip()
    if not _c:
        continue
    try:
        TRUSTED_PROXIES.append(ipaddress.ip_network(_c, strict=False))
    except ValueError:
        print(f"⚠️ Gateway: regla de proxy de confianza inválida: {_c}", file=sys.stderr, flush=True)


def resolve_client_ip(request: Request) -> str:
    """Resuelve la IP real del cliente de forma segura.

    Si la conexión directa NO proviene de un proxy en TRUSTED_PROXIES, se devuelve
    la IP del peer (la del socket, no falseable) y se IGNORAN por completo las
    cabeceras X-Real-Ip / X-Forwarded-For, que un cliente podría falsificar.

    Si proviene de un proxy de confianza, se recorre la cadena X-Forwarded-For de
    derecha a izquierda descartando proxies de confianza hasta la primera IP no
    confiable (el cliente real).
    """
    peer = (request.client.host if request.client else "") or ""

    # Sin proxies de confianza o sin peer -> usar la IP del socket.
    if not TRUSTED_PROXIES or not peer:
        return peer
    try:
        peer_obj = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_obj in net for net in TRUSTED_PROXIES):
        return peer

    # Conexión desde un proxy de confianza: analizar la cadena X-Forwarded-For.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        chain = [ip.strip() for ip in xff.split(",") if ip.strip()]
        for ip in reversed(chain):
            try:
                if any(ipaddress.ip_address(ip) in net for net in TRUSTED_PROXIES):
                    continue  # salto de proxies de confianza
            except ValueError:
                pass
            return ip  # primera IP no confiable desde la derecha
        return peer  # toda la cadena era de confianza

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return peer
