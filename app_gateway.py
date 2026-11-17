#!/usr/bin/env python3
"""
vLLM Suite Gateway - Root Entrypoint Wrapper.
Punto de entrada compatible para systemd (vllm-gateway.service).
Permite conmutación atómica entre el Gateway de producción (gateway/) y el
sandbox Router-Synthesizer (gateway2/) mediante GATEWAY_DISPATCHER_MODE.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

_mode = os.getenv("GATEWAY_DISPATCHER_MODE", "direct").strip().lower()

if _mode == "pre_rag":
    print("🚀 [Gateway Dispatcher] Modo 'pre_rag' activo -> Despachando a Gateway2 (Router-Synthesizer Sandbox)", file=sys.stderr, flush=True)
    from gateway2.server import main, run_servers
else:
    print("🛡️ [Gateway Dispatcher] Modo 'direct' activo -> Despachando a Gateway de Producción Canónico", file=sys.stderr, flush=True)
    from gateway.server import main, run_servers

if __name__ == "__main__":
    main()
