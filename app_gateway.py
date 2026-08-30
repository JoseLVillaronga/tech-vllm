#!/usr/bin/env python3
"""
vLLM Suite Gateway - Root Entrypoint Wrapper.
Punto de entrada compatible para systemd (vllm-gateway.service).
Delega la ejecución al paquete modular gateway.server.
"""
from gateway.server import main, run_servers

if __name__ == "__main__":
    main()
