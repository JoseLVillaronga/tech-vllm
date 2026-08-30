"""
Módulo core de seguridad, red y autenticación del Gateway.
"""
from gateway.core.ip_resolver import resolve_client_ip, TRUSTED_PROXIES
from gateway.core.fail2ban import register_failed_attempt
from gateway.core.ip_rules import sync_ip_rules_loop, is_ip_allowed
from gateway.core.auth import get_db, get_key_doc, validate_token_doc, extract_token, MASTER_KEY

__all__ = [
    "resolve_client_ip",
    "TRUSTED_PROXIES",
    "register_failed_attempt",
    "sync_ip_rules_loop",
    "is_ip_allowed",
    "get_db",
    "get_key_doc",
    "validate_token_doc",
    "extract_token",
    "MASTER_KEY"
]
