import os
import sys
import httpx
from typing import List, Optional

try:
    from config import API_KEY as MASTER_KEY
except ImportError:
    MASTER_KEY = os.getenv("API_KEY", "")


async def flush_llama_slots(target_port: int = 18100, max_slots: int = 2, timeout: float = 2.0) -> bool:
    """
    Solicita a llama-server el vaciado (erase) de la memoria KV cache en RAM de los slots activos.
    Se ejecuta de forma asíncrona y segura (no bloquea el Gateway ni interrumpe peticiones concurrentes).
    
    Args:
        target_port: Puerto local donde corre llama-server (ej: 18100).
        max_slots: Cantidad de slots por defecto si /slots no responde lista completa.
        timeout: Tiempo máximo de espera en segundos por operación.
        
    Returns:
        bool: True si al menos un slot fue vaciado exitosamente, False de lo contrario.
    """
    if not target_port:
        return False

    base_url = f"http://127.0.0.1:{target_port}"
    headers = {"Authorization": f"Bearer {MASTER_KEY}"} if MASTER_KEY else {}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 1. Intentar descubrir dinámicamente los slots activos
            slot_ids: List[int] = []
            try:
                slots_resp = await client.get(f"{base_url}/slots", headers=headers)
                if slots_resp.status_code == 200:
                    slots_data = slots_resp.json()
                    if isinstance(slots_data, list):
                        slot_ids = [s.get("id") for s in slots_data if isinstance(s, dict) and "id" in s]
            except Exception:
                pass

            if not slot_ids:
                slot_ids = list(range(max(1, max_slots)))

            # 2. Enviar acción de vaciado (erase) a cada slot
            erased_count = 0
            for slot_id in slot_ids:
                try:
                    erase_url = f"{base_url}/slots/{slot_id}?action=erase"
                    resp = await client.post(erase_url, headers=headers)
                    if resp.status_code == 200:
                        erased_count += 1
                    elif resp.status_code == 501:
                        # llama-server corriendo sin --slot-save-path
                        print(
                            f"⚠️ [Slot Flusher] llama-server en puerto {target_port} retornó 501: "
                            f"requiere iniciarse con '--slot-save-path'.",
                            file=sys.stderr,
                            flush=True
                        )
                        return False
                except Exception as slot_err:
                    print(
                        f"⚠️ [Slot Flusher] No se pudo vaciar slot {slot_id} en puerto {target_port}: {slot_err}",
                        file=sys.stderr,
                        flush=True
                    )

            if erased_count > 0:
                print(
                    f"🧹 [Slot Flusher] Memoria RAM liberada: {erased_count} slot(s) de KV cache vaciados en llama-server (puerto {target_port}).",
                    file=sys.stderr,
                    flush=True
                )
                return True
            return False

    except Exception as e:
        print(
            f"⚠️ [Slot Flusher] Error al comunicar con backend llama-server en puerto {target_port}: {e}",
            file=sys.stderr,
            flush=True
        )
        return False
