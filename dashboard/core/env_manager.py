import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = str(REPO_ROOT / ".env")


def read_env_file():
    """
    Lee las líneas del archivo .env preservando el formato original y comentarios.
    """
    if not os.path.exists(ENV_PATH):
        return []
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        return f.readlines()


def parse_env_to_dict():
    """
    Parsea las variables de entorno en un diccionario simple, ignorando comentarios.
    """
    lines = read_env_file()
    env_vars = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            parts = stripped.split("=", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            # Eliminar comillas externas si existen
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            env_vars[key] = val
    return env_vars


def save_env_from_dict(new_values):
    """
    Guarda las nuevas variables de entorno en el archivo .env,
    preservando el resto de las líneas y comentarios.
    """
    lines = read_env_file()
    updated_lines = []
    keys_written = set()
    
    # Recorrer el archivo original y actualizar claves existentes
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in new_values:
                val = new_values[key]
                # Envolver en comillas si es una cadena de modelo, alias o tiene espacios
                if key in ["MODEL", "VLLM_ALIAS", "LLAMA_ALIAS"] or " " in str(val):
                    updated_lines.append(f'{key}="{val}"\n')
                else:
                    updated_lines.append(f'{key}={val}\n')
                keys_written.add(key)
                continue
        updated_lines.append(line)
        
    # Escribir las claves que son totalmente nuevas
    for key, val in new_values.items():
        if key not in keys_written:
            if key in ["MODEL", "VLLM_ALIAS", "LLAMA_ALIAS"] or " " in str(val):
                updated_lines.append(f'{key}="{val}"\n')
            else:
                updated_lines.append(f'{key}={val}\n')
                
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)
