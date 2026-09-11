from datetime import datetime, timezone

def check_and_reset_key_quota_dict(k: dict, db) -> dict:
    """Verifica si corresponde reiniciar la cuota (diaria o mensual) de una clave API y la resetea si aplica."""
    quota_reset = k.get("quota_reset", "none")
    if quota_reset in ["daily", "monthly"]:
        last_reset_at = k.get("last_reset_at")
        now = datetime.now(timezone.utc)
        reset_needed = False
        
        if not last_reset_at:
            reset_needed = True
        else:
            if isinstance(last_reset_at, str):
                try:
                    last_dt = datetime.fromisoformat(last_reset_at.replace("Z", "+00:00"))
                except Exception:
                    last_dt = now
            elif isinstance(last_reset_at, datetime):
                last_dt = last_reset_at
            else:
                last_dt = now
                
            if quota_reset == "daily":
                if now.date() > last_dt.date():
                    reset_needed = True
            elif quota_reset == "monthly":
                if (now.year, now.month) > (last_dt.year, last_dt.month):
                    reset_needed = True
                    
        if reset_needed:
            db.api_keys.update_one(
                {"_id": k["_id"]},
                {"$set": {"used_tokens": 0, "last_reset_at": now}}
            )
            k["used_tokens"] = 0
            k["last_reset_at"] = now
    return k
