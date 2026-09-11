import re

def slugify_provider_name(name: str) -> str:
    """Convierte un nombre arbitrario de proveedor en un slug seguro para identificadores y URLs."""
    slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip().lower()).strip('_')
    return slug or "cloud"
