"""
Módulo del motor de proxying inverso y streaming.
"""
from gateway2.proxy.proxy_factory import create_proxy_app, get_http_client, close_http_client

__all__ = ["create_proxy_app", "get_http_client", "close_http_client"]
