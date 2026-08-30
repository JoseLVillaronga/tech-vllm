import sys
import asyncio
import ipaddress
from pymongo import MongoClient
from config import get_mongo_uri, MONGO_DB

cached_whitelist = []
cached_blacklist = []


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


def is_ip_allowed(client_ip_obj: ipaddress._BaseAddress) -> tuple[bool, str]:
    """
    Verifica si una IP tiene permitido el paso según las listas en memoria.
    Retorna (is_allowed, reason).
    """
    global cached_whitelist, cached_blacklist
    
    # 1. Comprobar Lista Negra (Blacklist)
    if any(client_ip_obj in net for net in cached_blacklist):
        return False, "IP Bloqueada en Lista Negra."
        
    # 2. Comprobar Lista Blanca (Whitelist) si está activa
    if cached_whitelist:
        if not any(client_ip_obj in net for net in cached_whitelist):
            return False, "IP no autorizada en Lista Blanca."
            
    return True, "OK"


async def sync_ip_rules_loop():
    """
    Lazo en segundo plano para sincronizar las reglas de IP desde MongoDB cada 10s.
    """
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
