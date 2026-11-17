"""
Módulo de telemetría, métricas y auditoría del Gateway.
"""
from gateway2.telemetry.usage_logger import save_usage_log
from gateway2.telemetry.blocked_logger import save_blocked_request_log

__all__ = ["save_usage_log", "save_blocked_request_log"]
