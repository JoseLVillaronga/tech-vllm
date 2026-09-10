import os
import sys
import asyncio
import ipaddress
from gateway.core.database import get_db

cached_whitelist = []
cached_blacklist = []
blacklist_notice_counts: dict[str, int] = {}


def get_blacklist_max_notices() -> int:
    """
    Devuelve la cantidad máxima de advertencias formales 403 antes de activar el silent drop.
    """
    try:
        return int(os.getenv("BLACKLIST_MAX_NOTICES", "3"))
    except ValueError:
        return 3


def get_blacklist_notice_count(ip_str: str) -> int:
    """Consulta la cantidad de avisos enviados a una IP en lista negra (para métricas y tests)."""
    return blacklist_notice_counts.get(ip_str, 0)


def clear_blacklist_notice_counts():
    """Limpia el registro de avisos de lista negra (útil para tests o reseteo administrativo)."""
    global blacklist_notice_counts
    blacklist_notice_counts.clear()


def check_ip_access(client_ip_obj: ipaddress._BaseAddress) -> tuple[bool, str, bool]:
    """
    Verifica si una IP tiene permitido el paso según las listas en memoria.
    Retorna (is_allowed, reason, should_silent_drop).

    - Si la IP está en la lista negra:
      Incrementa el contador de avisos para esa IP.
      Si ha superado BLACKLIST_MAX_NOTICES, retorna (False, reason, True) indicando drop silencioso.
      Si aún no lo supera, retorna (False, reason, False) para emitir el error formal 403.
    - Si la IP no está autorizada por la lista blanca activa:
      Retorna (False, reason, False).
    - Si el acceso es válido:
      Retorna (True, "OK", False).
    """
    global cached_whitelist, cached_blacklist, blacklist_notice_counts

    # 1. Comprobar Lista Negra (Blacklist)
    if any(client_ip_obj in net for net in cached_blacklist):
        ip_str = str(client_ip_obj)
        current_count = blacklist_notice_counts.get(ip_str, 0) + 1
        blacklist_notice_counts[ip_str] = current_count
        max_notices = get_blacklist_max_notices()
        should_silent_drop = current_count > max_notices
        return False, "IP Bloqueada en Lista Negra.", should_silent_drop

    # 2. Comprobar Lista Blanca (Whitelist) si está activa
    if cached_whitelist:
        if not any(client_ip_obj in net for net in cached_whitelist):
            return False, "IP no autorizada en Lista Blanca.", False

    return True, "OK", False


def is_ip_allowed(client_ip_obj: ipaddress._BaseAddress) -> tuple[bool, str]:
    """
    Compatibilidad hacia atrás con contratos existentes.
    Retorna (is_allowed, reason).
    """
    allowed, reason, _ = check_ip_access(client_ip_obj)
    return allowed, reason


async def sync_ip_rules_loop():
    """
    Lazo en segundo plano para sincronizar las reglas de IP desde MongoDB cada 10s.
    """
    global cached_whitelist, cached_blacklist, blacklist_notice_counts
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

            # Purgar contadores de IPs que ya no coinciden con ninguna regla activa de lista negra
            if blacklist_notice_counts:
                active_banned_ips = set()
                for ip_str in list(blacklist_notice_counts.keys()):
                    try:
                        ip_obj = ipaddress.ip_address(ip_str)
                        if any(ip_obj in net for net in new_blacklist):
                            active_banned_ips.add(ip_str)
                    except Exception:
                        pass
                for ip_str in list(blacklist_notice_counts.keys()):
                    if ip_str not in active_banned_ips:
                        blacklist_notice_counts.pop(ip_str, None)

        except Exception as e:
            print(f"⚠️ Error al sincronizar reglas de IP: {e}", file=sys.stderr, flush=True)

        await asyncio.sleep(10)
