#!/usr/bin/env python3
"""
vLLM Suite Administration Dashboard - Entrypoint Wrapper.

Este archivo mantiene 100% de retrocompatibilidad con servicios systemd
(vllm-dashboard.service) y scripts existentes delegando la ejecución
a la arquitectura modular en el paquete `dashboard/`.
"""

from dashboard.app import app, create_app, main, PORT
from dashboard.core import (
    REPO_ROOT,
    ENV_PATH,
    SERVICES,
    SERVICE_PORTS,
    BACKEND_PORTS,
    get_gpu_info,
    get_cpu_temperature,
    get_service_status,
    control_service,
    read_env_file,
    parse_env_to_dict,
    save_env_from_dict,
    init_db_telemetry,
    start_telemetry_collector,
    get_db,
    slugify_provider_name,
    resample_audio_to_24k_mono,
    check_and_reset_key_quota_dict,
)

if __name__ == "__main__":
    main()
