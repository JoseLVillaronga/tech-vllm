"""
Módulo central del Dashboard (acceso a bases de datos, métricas, variables de entorno, telemetría y utilitarios).
"""

from .database import get_db, get_mongo_uri, MONGO_DB
from .system_metrics import (
    SERVICES,
    SERVICE_PORTS,
    BACKEND_PORTS,
    get_gpu_info,
    get_cpu_temperature,
    get_service_status,
    control_service
)
from .env_manager import (
    REPO_ROOT,
    ENV_PATH,
    read_env_file,
    parse_env_to_dict,
    save_env_from_dict
)
from .telemetry_service import (
    init_db_telemetry,
    start_telemetry_collector
)
from .provider_utils import slugify_provider_name
from .audio_utils import resample_audio_to_24k_mono
from .quota_utils import check_and_reset_key_quota_dict
from .auth_service import (
    resolve_client_ip_dashboard,
    is_localhost_ip,
    is_localhost_request,
    verify_credentials,
    list_dashboard_users,
    create_dashboard_user,
    update_dashboard_user,
    reset_dashboard_user_password,
    delete_dashboard_user,
    login_user_session,
    logout_user_session,
    get_current_user,
    login_required,
    admin_required
)

__all__ = [
    "get_db",
    "get_mongo_uri",
    "MONGO_DB",
    "SERVICES",
    "SERVICE_PORTS",
    "BACKEND_PORTS",
    "get_gpu_info",
    "get_cpu_temperature",
    "get_service_status",
    "control_service",
    "REPO_ROOT",
    "ENV_PATH",
    "read_env_file",
    "parse_env_to_dict",
    "save_env_from_dict",
    "init_db_telemetry",
    "start_telemetry_collector",
    "slugify_provider_name",
    "resample_audio_to_24k_mono",
    "check_and_reset_key_quota_dict",
    "resolve_client_ip_dashboard",
    "is_localhost_ip",
    "is_localhost_request",
    "verify_credentials",
    "list_dashboard_users",
    "create_dashboard_user",
    "update_dashboard_user",
    "reset_dashboard_user_password",
    "delete_dashboard_user",
    "login_user_session",
    "logout_user_session",
    "get_current_user",
    "login_required",
    "admin_required"
]
