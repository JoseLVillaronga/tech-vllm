import os
import time
import sys
import asyncio
import ipaddress
from datetime import datetime, timedelta, timezone
from gateway.core.database import get_db

# Control de intrusión (Fail2ban nativo en memoria)
failed_attempts = {}
failed_attempts_lock = asyncio.Lock()


def get_fail2ban_config() -> tuple[int, int, int]:
    """
    Obtiene la configuración de Fail2ban desde variables de entorno con fallbacks seguros.
    Retorna (max_failures, window_seconds, ban_hours).
    """
    try:
        max_failures = int(os.getenv("FAIL2BAN_MAX_FAILURES", "3"))
    except ValueError:
        max_failures = 3

    try:
        window_seconds = int(os.getenv("FAIL2BAN_WINDOW_SECONDS", "300"))
    except ValueError:
        window_seconds = 300

    try:
        ban_hours = int(os.getenv("FAIL2BAN_BAN_HOURS", "48"))
    except ValueError:
        ban_hours = 48

    return max_failures, window_seconds, ban_hours


def should_exclude_loopback() -> bool:
    """
    Indica si las direcciones loopback (127.0.0.0/8, ::1) están exentas de auto-baneo por Fail2ban.
    Por defecto es True para prevenir auto-bloqueos accidentales (Self-DoS).
    """
    return os.getenv("FAIL2BAN_EXCLUDE_LOOPBACK", "true").strip().lower() in ["true", "1", "yes"]


async def register_failed_attempt(client_ip: str):
    """
    Registra un intento de acceso no autorizado y aplica baneo automático
    en MongoDB si se acumulan max_failures en la ventana de window_seconds.
    """
    if should_exclude_loopback():
        try:
            if ipaddress.ip_address(client_ip).is_loopback:
                return
        except ValueError:
            pass

    max_failures, window_seconds, ban_hours = get_fail2ban_config()
    now = time.time()
    async with failed_attempts_lock:
        history = failed_attempts.get(client_ip, [])
        # Filtrar intentos dentro de la ventana configurada
        history = [t for t in history if now - t < window_seconds]
        history.append(now)
        failed_attempts[client_ip] = history

        if len(history) >= max_failures:
            # Bloquear automáticamente en MongoDB
            try:
                db = get_db()
                ban_until = datetime.now(timezone.utc) + timedelta(hours=ban_hours)
                db.ip_rules.update_one(
                    {"network": client_ip},
                    {
                        "$set": {
                            "network": client_ip,
                            "action": "blacklist",
                            "description": f"Auto-ban Fail2ban ({max_failures} intentos fallidos en {window_seconds}s)",
                            "is_active": True,
                            "created_at": datetime.now(timezone.utc),
                            "expires_at": ban_until
                        }
                    },
                    upsert=True
                )
                print(
                    f"🚨 Fail2ban: IP {client_ip} bloqueada automáticamente por {ban_hours} horas "
                    f"tras {max_failures} fallos en {window_seconds} segundos.",
                    file=sys.stderr,
                    flush=True
                )
                # Limpiar historial para evitar re-bloqueos en bucle
                failed_attempts.pop(client_ip, None)
            except Exception as ban_err:
                print(f"⚠️ Error aplicando regla de auto-ban en MongoDB para {client_ip}: {ban_err}", file=sys.stderr, flush=True)
