"""
Módulo core de seguridad, red y autenticación del Gateway.
"""
from gateway.core.ip_resolver import resolve_client_ip, TRUSTED_PROXIES
from gateway.core.fail2ban import register_failed_attempt, should_exclude_loopback
from gateway.core.ip_rules import sync_ip_rules_loop, is_ip_allowed, check_ip_access
from gateway.core.auth import get_db, get_key_doc, validate_token_doc, extract_token, MASTER_KEY
from gateway.core.context_pruner import prune_chat_history, get_max_user_turns, get_max_context_tokens
from gateway.core.slot_flusher import flush_llama_slots
from gateway.core.alignment_engine import (
    enrich_chat_payload,
    format_company_profile_block,
    get_invariants_system_prompt,
    get_alignment_settings,
    save_alignment_settings,
    sync_alignment_settings_loop
)

__all__ = [
    "resolve_client_ip",
    "TRUSTED_PROXIES",
    "register_failed_attempt",
    "should_exclude_loopback",
    "sync_ip_rules_loop",
    "is_ip_allowed",
    "check_ip_access",
    "get_db",
    "get_key_doc",
    "validate_token_doc",
    "extract_token",
    "MASTER_KEY",
    "enrich_chat_payload",
    "format_company_profile_block",
    "get_invariants_system_prompt",
    "get_alignment_settings",
    "save_alignment_settings",
    "sync_alignment_settings_loop",
    "prune_chat_history",
    "get_max_user_turns",
    "get_max_context_tokens",
    "flush_llama_slots"
]
