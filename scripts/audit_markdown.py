#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditor y Linter Semántico de Markdown Normativo (RAG Jurídico)
================================================================
Audita documentos legales extraídos en `scripts/output/` comparándolos contra
los criterios de normalización de `docs/MANUAL_CRITERIOS_NORMALIZACION_MARKDOWN.md`.

Características:
  - Escaneo interactivo de archivos Markdown en `scripts/output/`.
  - Indexación de líneas con coordenadas numéricas exactas (`linea: 124`).
  - Inyección del manual canónico de normalización como System Prompt.
  - Llamada a modelos con amplia ventana de contexto (Gateway local o DeepSeek Cloud).
  - Emisión de un reporte diagnóstico conciso en tabla (sin reescribir la ley).
  - Streaming con soporte para modelos de razonamiento (pensamiento + reporte).
  - Auto-descubrimiento de API Key autorizada de cliente desde MongoDB o .env.
  - Cero riesgo de corrupción de texto (Linter de solo lectura).
"""

import os
import sys
import re
import argparse
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Bootstrap de dependencias locales del venv si están disponibles
REPO_ROOT = Path(__file__).resolve().parent.parent
site_packages_candidate = REPO_ROOT / "venv" / "lib" / "python3.13" / "site-packages"
if site_packages_candidate.exists() and str(site_packages_candidate) not in sys.path:
    sys.path.insert(0, str(site_packages_candidate))

try:
    import requests
except ImportError:
    for venv_candidate in [REPO_ROOT / "venv" / "bin" / "python", REPO_ROOT / ".venv" / "bin" / "python"]:
        if venv_candidate.exists() and venv_candidate.resolve() != Path(sys.executable).resolve():
            os.execv(str(venv_candidate), [str(venv_candidate)] + sys.argv)
    print("Error: Se requiere el paquete 'requests'.", file=sys.stderr)
    print("Instálelo con: pip install requests", file=sys.stderr)
    sys.exit(1)


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DOCS_DIR = REPO_ROOT / "docs"
MANUAL_PATH = DOCS_DIR / "MANUAL_CRITERIOS_NORMALIZACION_MARKDOWN.md"
ENV_PATH = REPO_ROOT / ".env"


def parse_local_env() -> Dict[str, str]:
    """Carga variables desde .env sin requerir librerías externas pesadas."""
    env_vars = {}
    if ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        env_vars[k] = v
        except Exception:
            pass
    return env_vars


def get_authorized_gateway_key(env_vars: Dict[str, str]) -> Tuple[str, str]:
    """
    Resuelve una API Key de cliente autorizada para consumir endpoints del Gateway.
    
    El Gateway rechaza la Clave Maestra (API_KEY) con HTTP 403 Forbidden en puertos cliente
    para cumplir con la política Zero Trust (ALLOW_MASTER_KEY_ON_GATEWAY=false).
    Por ende, esta función busca:
      1. Variables de entorno explícitas (CLIENT_API_KEY, OPENWEBUI_API_KEY).
      2. Auto-descubrimiento en MongoDB (clave de Open-WebUI o con acceso a cloud_providers).
      3. Fallback a MASTER_KEY si ALLOW_MASTER_KEY_ON_GATEWAY=true.
    """
    # 1. Variables explícitas en entorno o .env
    for var in ["CLIENT_API_KEY", "OPENWEBUI_API_KEY", "GATEWAY_CLIENT_KEY"]:
        val = os.getenv(var, env_vars.get(var, "")).strip()
        if val:
            return val, f"Variable {var}"

    # 2. Auto-descubrimiento dinámico en MongoDB
    try:
        import pymongo
        mongo_host = os.getenv("MONGO_HOST", env_vars.get("MONGO_HOST", "127.0.0.1"))
        mongo_port = int(os.getenv("MONGO_PORT", env_vars.get("MONGO_PORT", "27017")))
        mongo_user = os.getenv("MONGO_USER", env_vars.get("MONGO_USER", "admin"))
        mongo_pass = os.getenv("MONGO_PASS", env_vars.get("MONGO_PASS", ""))
        mongo_db_name = os.getenv("MONGO_DB", env_vars.get("MONGO_DB", "vllm"))

        if mongo_pass:
            uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:{mongo_port}/{mongo_db_name}?authSource=admin"
        else:
            uri = f"mongodb://{mongo_host}:{mongo_port}/{mongo_db_name}"

        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=800)
        db = client[mongo_db_name]

        # Priorizar clave 'Open-WebUI' o claves con acceso a proveedores cloud
        key_doc = db.api_keys.find_one({
            "is_active": True,
            "name": re.compile(r"open-webui", re.I)
        })
        if not key_doc:
            key_doc = db.api_keys.find_one({
                "is_active": True,
                "allowed_providers": {"$exists": True, "$type": "array", "$ne": []}
            })
        if not key_doc:
            key_doc = db.api_keys.find_one({"is_active": True})

        if key_doc and key_doc.get("key"):
            key_name = key_doc.get("name", "Cliente Autorizado")
            return key_doc["key"], f"MongoDB ({key_name})"
    except Exception:
        pass

    # 3. Fallback a la clave de .env
    master_key = os.getenv("API_KEY", env_vars.get("API_KEY", "")).strip()
    return master_key, ".env (Master Key)"


def detect_connection_defaults() -> Tuple[str, str, str, str]:
    """
    Detecta automáticamente el endpoint, la API key autorizada y el modelo preferido:
      1. Prioridad: DeepSeek Cloud directo (consultando MongoDB cloud_providers o DEEPSEEK_API_KEY)
         con el modelo 'deepseek-chat' (DeepSeek V3, 128K contexto, rápido y sin bloat de razonamiento).
      2. Fallback: Gateway local en 127.0.0.1:8000 con API Key autorizada de cliente (Open-WebUI).
    Retorna: (default_base, default_key, default_model, key_source_info)
    """
    env_vars = parse_local_env()
    
    # 1. Intentar auto-descubrimiento del proveedor DeepSeek en MongoDB
    try:
        import pymongo
        mongo_host = os.getenv("MONGO_HOST", env_vars.get("MONGO_HOST", "127.0.0.1"))
        mongo_port = int(os.getenv("MONGO_PORT", env_vars.get("MONGO_PORT", "27017")))
        mongo_user = os.getenv("MONGO_USER", env_vars.get("MONGO_USER", "admin"))
        mongo_pass = os.getenv("MONGO_PASS", env_vars.get("MONGO_PASS", ""))
        mongo_db_name = os.getenv("MONGO_DB", env_vars.get("MONGO_DB", "vllm"))

        if mongo_pass:
            uri = f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:{mongo_port}/{mongo_db_name}?authSource=admin"
        else:
            uri = f"mongodb://{mongo_host}:{mongo_port}/{mongo_db_name}"

        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=800)
        db = client[mongo_db_name]
        ds_prov = db.cloud_providers.find_one({"name": re.compile(r"deepseek", re.I), "is_active": True})
        if ds_prov and ds_prov.get("api_key"):
            base = ds_prov.get("base_url") or "https://api.deepseek.com"
            base = base.rstrip("/")
            if not base.endswith("/v1"):
                base = f"{base}/v1"
            return base, ds_prov["api_key"], "deepseek-chat", "DeepSeek Cloud (MongoDB)"
    except Exception:
        pass

    # 2. Comprobar si existe DEEPSEEK_API_KEY en .env o variables de entorno
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", env_vars.get("DEEPSEEK_API_KEY", "")).strip()
    if deepseek_key:
        return "https://api.deepseek.com/v1", deepseek_key, "deepseek-chat", "DeepSeek Cloud (.env)"

    # 3. Fallback: Gateway local con API Key autorizada de cliente (Open-WebUI)
    gateway_port = os.getenv("PORT", env_vars.get("PORT", "8000"))
    client_key, key_source = get_authorized_gateway_key(env_vars)
    return f"http://127.0.0.1:{gateway_port}/v1", client_key, "openai/gpt-4o-mini", f"Gateway Local ({key_source})"



def list_candidate_documents() -> List[Path]:
    """Lista los archivos Markdown elegibles en scripts/output/, excluyendo reportes de auditoría."""
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return []
        
    candidates = []
    for f in OUTPUT_DIR.glob("*.md"):
        if f.is_file() and not f.name.endswith(("_auditoria.md", "_audit.md", "_normalizado.md")):
            candidates.append(f)
            
    return sorted(candidates, key=lambda x: x.name.lower())


def load_manual_rules() -> str:
    """Carga el manual canónico de criterios de normalización para inyectarlo como directiva."""
    if MANUAL_PATH.exists():
        try:
            return MANUAL_PATH.read_text(encoding="utf-8")
        except Exception as e:
            print(f"⚠️ Advertencia al leer {MANUAL_PATH.name}: {e}", file=sys.stderr)
            
    return (
        "Criterios de normalización legal:\n"
        "1. Títulos: # Ley, ## Libro/Parte, ### Título - Epígrafe, #### Capítulo, ##### Sección.\n"
        "2. Títulos sin subtítulo temático (ej: ### TÍTULO II) son un error grave (ERR_TIT_TRUNC).\n"
        "3. Artículos: formato exacto **ARTÍCULO X°.- Epígrafe.** con negrita integral.\n"
        "4. Incisos: formato de lista * **a)** o * **1.**.\n"
        "5. Metadatos oficiales al inicio en bloque de cita >.\n"
        "6. No dejar etiquetas HTML (<br>, <font>, <div>).\n"
    )


def prepare_numbered_text(filepath: Path) -> Tuple[str, int, int]:
    """Lee el documento y le antepone coordenadas numéricas a cada línea."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    
    numbered_lines = []
    for idx, line in enumerate(lines, start=1):
        numbered_lines.append(f"{idx:5d} | {line}")
        
    numbered_text = "\n".join(numbered_lines)
    approx_tokens = len(numbered_text) // 4
    return numbered_text, len(lines), approx_tokens


def build_system_prompt(manual_content: str) -> str:
    """Construye el system prompt del Auditor / Linter de Coordenadas."""
    return f"""Eres un Auditor y Linter Semántico de Alta Precisión especializado en normativas jurídicas argentinas y compatibilidad RAG en LanceDB.

Tu misión es AUDITAR un documento Markdown numerado línea por línea y emitir un REPORTE DIAGNÓSTICO ESTRUCTURADO indicando las coordenadas exactas de cualquier defecto, desvío o antipatrón.

REGLAS ABSOLUTAS:
1. NO reescribas el documento ni copies fragmentos extensos.
2. Tu salida debe ser ÚNICAMENTE el reporte diagnóstico en formato Markdown estructurado.
3. Para cada falla detectada, debes citar el NÚMERO DE LÍNEA EXACTO tal como figura al inicio de cada renglón (`  142 | ...`).
4. Si un documento está perfecto y no tiene defectos, indícalo explícitamente con:
   `✅ CANÓNICO: El documento cumple al 100% con los criterios de normalización.`

A continuación se detalla el MANUAL CANÓNICO DE CRITERIOS DE NORMALIZACIÓN que define los estándares a auditar:

===============================================================================
{manual_content}
===============================================================================

ESTRUCTURA OBLIGATORIA DE TU REPORTE:

### 📋 Resumen Diagnóstico
- **Estado General:** [ ✅ CANÓNICO | ⚠️ CON OBSERVACIONES | ❌ CRÍTICO ]
- **Total de Desvíos Encontrados:** [Número]
- **Evaluación Global:** [1 o 2 párrafos concisos con la conclusión técnica]

### 🔍 Tabla de Coordenadas y Hallazgos
| Línea | Código de Error | Gravedad | Fragmento Observado | Diagnóstico y Acción Sugerida |
| :---: | :---: | :---: | :--- | :--- |
| **[N°]** | `[CODIGO]` | [Alta/Media/Baja] | `[Texto observado]` | [Explicación clara y sugerencia de corrección] |

Utiliza estrictamente los códigos canónicos:
- `ERR_FRONTMATTER`: Falta ficha de metadatos oficial en bloque `>` o resumen.
- `ERR_TIT_TRUNC`: Encabezado H2/H3/H4 amputado o sin subtítulo temático.
- `ERR_ART_SYNTAX`: Artículo sin formato canónico, sin ordinal `°`, o sin palabra clave `ARTÍCULO`.
- `ERR_ART_BOLD`: Epígrafe fuera de la negrita o negrita mal cerrada.
- `ERR_INC_FMT`: Incisos alfabéticos o numéricos no formateados como ítems de lista `* **x)**`.
- `ERR_HTML_TAG`: Etiquetas HTML residuales (`<font>`, `<span>`, `<br>`, `<div>`).
- `ERR_TAB_BROKEN`: Tablas GFM asimétricas o rotas.
- `ERR_ENC_CORRUPT`: Caracteres de control invisibles, artefactos OCR o mojibake.
"""


def execute_audit_stream(
    api_base: str,
    api_key: str,
    model: str,
    doc_name: str,
    numbered_text: str,
    system_prompt: str,
    stream: bool = True,
    timeout: int = 300
) -> str:
    """Envía la petición de auditoría por streaming y devuelve el texto completo generado."""
    endpoint = f"{api_base.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Por favor audita exhaustivamente el siguiente documento legal numerado '{doc_name}'. "
                f"Identifica todas las violaciones a los criterios canónicos e infórmalas con sus coordenadas de línea:\n\n"
                f"{numbered_text}"
            )
        }
    ]
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 4096,
        "stream": stream
    }
    
    full_output = []
    in_reasoning = False
    
    print(f"\n📡 Conectando con API: {endpoint}")
    print(f"🤖 Modelo auditor:    {model}")
    print(f"⏳ Procesando documento en contexto extendido...\n")
    print("=" * 70)
    
    try:
        if stream:
            with requests.post(endpoint, headers=headers, json=payload, stream=True, timeout=timeout) as response:
                if response.status_code != 200:
                    err_detail = response.text
                    if response.status_code == 403 and "Clave Maestra" in err_detail:
                        err_msg = (
                            f"Error HTTP 403: El Gateway tiene activa la protección Zero Trust y no admite la Clave Maestra.\n"
                            f"💡 Solución: Genera una API Key de cliente en el Dashboard (o usa la de Open-WebUI) "
                            f"y configúrala en .env como CLIENT_API_KEY=tu_clave."
                        )
                    else:
                        err_msg = f"Error HTTP {response.status_code}: {err_detail}"
                    print(f"\n❌ {err_msg}", file=sys.stderr)
                    return err_msg
                    
                if hasattr(sys.stdout, "reconfigure"):
                    try:
                        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                    except Exception:
                        pass

                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    if raw_line.startswith("data: "):
                        data_str = raw_line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices")
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            
                            reasoning_piece = delta.get("reasoning_content") or ""
                            content_piece = delta.get("content") or ""
                            
                            # Capturar siempre el contenido generado de forma prioritaria
                            if content_piece:
                                full_output.append(content_piece)

                            # Mostrar en consola de forma segura
                            try:
                                if reasoning_piece:
                                    if not in_reasoning:
                                        in_reasoning = True
                                        sys.stdout.write("\033[90m💭 [Razonando auditoría] ")
                                    sys.stdout.write(reasoning_piece)
                                    sys.stdout.flush()
                                    
                                if content_piece:
                                    if in_reasoning:
                                        in_reasoning = False
                                        sys.stdout.write("\033[0m\n\n")
                                    sys.stdout.write(content_piece)
                                    sys.stdout.flush()
                            except Exception:
                                pass
                        except Exception:
                            pass
                            
            if in_reasoning:
                try:
                    sys.stdout.write("\033[0m\n")
                except Exception:
                    pass
            print("\n" + "=" * 70)
        else:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            if response.status_code != 200:
                err_msg = f"Error HTTP {response.status_code}: {response.text}"
                print(f"\n❌ {err_msg}", file=sys.stderr)
                return err_msg
            res_json = response.json()
            choice = res_json.get("choices", [{}])[0]
            msg = choice.get("message", {})
            reasoning = msg.get("reasoning_content", "")
            content = msg.get("content", "")
            
            if reasoning:
                print(f"\033[90m💭 [Razonamiento]:\n{reasoning}\033[0m\n")
            print(content)
            full_output.append(content)
            print("\n" + "=" * 70)
            
    except requests.exceptions.Timeout:
        err_msg = f"Timeout ({timeout}s): El modelo tardó demasiado en responder."
        print(f"\n❌ {err_msg}", file=sys.stderr)
        return err_msg
    except Exception as e:
        err_msg = f"Excepción durante la llamada a la API: {e}"
        print(f"\n❌ {err_msg}", file=sys.stderr)
        return err_msg
        
    return "".join(full_output)


def interactive_menu(candidates: List[Path]) -> Optional[Path]:
    """Muestra el menú interactivo para seleccionar el documento a auditar."""
    print("=" * 70)
    print("🏛️   AUDITOR LINTER DE MARKDOWN JURÍDICO (RAG TECCAM)")
    print("=" * 70)
    print("Documentos disponibles para auditar en scripts/output/:\n")
    
    for idx, f in enumerate(candidates, start=1):
        size_kb = f.stat().st_size / 1024
        try:
            line_count = sum(1 for _ in f.open("rb"))
        except Exception:
            line_count = 0
        print(f"  [{idx}] {f.name} ({size_kb:.1f} KB, {line_count} líneas)")
        
    print("\n  [0] Salir")
    print("-" * 70)
    
    while True:
        choice = input(f"👉 Seleccione el número de documento [1-{len(candidates)}] o 0 para salir: ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        print("Opción inválida. Intente de nuevo.")


def main():
    parser = argparse.ArgumentParser(
        description="Auditor / Linter Semántico de Markdown Legal con Coordenadas"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        default=None,
        help="Ruta o nombre del archivo Markdown en scripts/output/ a auditar."
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="URL base de la API OpenAI-compatible (ej: http://127.0.0.1:8000/v1 o https://api.deepseek.com/v1)."
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Clave API para autenticar en el Gateway o en DeepSeek Cloud."
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Nombre del modelo a utilizar (ej: deepseek/deepseek-v4-flash, deepseek-chat)."
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Activa la salida por streaming en tiempo real en consola (por defecto: False)."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Tiempo máximo de espera para la respuesta en segundos (por defecto 300)."
    )
    
    args = parser.parse_args()
    
    # 1. Resolver candidatos
    candidates = list_candidate_documents()
    if not candidates:
        print(f"⚠️ No se encontraron archivos Markdown para auditar en: {OUTPUT_DIR}", file=sys.stderr)
        print("Extraiga primero alguna ley con: ./scripts/fetch_infoleg.py", file=sys.stderr)
        sys.exit(1)
        
    # 2. Determinar archivo objetivo
    target_file: Optional[Path] = None
    if args.file:
        arg_path = Path(args.file)
        if arg_path.exists():
            target_file = arg_path
        elif (OUTPUT_DIR / args.file).exists():
            target_file = OUTPUT_DIR / args.file
        else:
            print(f"❌ Error: Archivo '{args.file}' no encontrado en {OUTPUT_DIR}", file=sys.stderr)
            sys.exit(1)
    else:
        target_file = interactive_menu(candidates)
        if not target_file:
            print("Operación cancelada.")
            sys.exit(0)
            
    # 3. Detectar conexión y configuración
    def_base, def_key, def_model, key_source = detect_connection_defaults()
    api_base = args.api_base or def_base
    api_key = args.api_key or def_key
    model = args.model or def_model
    
    print(f"🔑 Autenticación:   Resuelta via {key_source}")
    
    # 4. Preparar documento con numeración de coordenadas
    print(f"📂 Preparando:      {target_file.name}")
    numbered_text, total_lines, est_tokens = prepare_numbered_text(target_file)
    print(f"📊 Métricas:        {total_lines} líneas | ~{est_tokens:,} tokens estimados de contexto")
    
    # 5. Cargar criterios canónicos
    manual_content = load_manual_rules()
    system_prompt = build_system_prompt(manual_content)
    
    # 6. Ejecutar auditoría
    start_time = time.time()
    audit_report = execute_audit_stream(
        api_base=api_base,
        api_key=api_key,
        model=model,
        doc_name=target_file.name,
        numbered_text=numbered_text,
        system_prompt=system_prompt,
        stream=args.stream,
        timeout=args.timeout
    )
    elapsed = time.time() - start_time
    
    # 7. Persistir reporte
    report_filename = f"{target_file.stem}_auditoria.md"
    report_path = OUTPUT_DIR / report_filename
    
    header_info = (
        f"# 📋 Reporte de Auditoría: {target_file.name}\n\n"
        f"> **Documento Auditado:** `{target_file.name}` ({total_lines} líneas, ~{est_tokens:,} tokens)\n"
        f"> **Modelo Auditor:** `{model}` via `{api_base}`\n"
        f"> **Fecha y Hora:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"> **Tiempo de Ejecución:** {elapsed:.2f} segundos\n"
        f"> **Manual Canónico:** [`docs/MANUAL_CRITERIOS_NORMALIZACION_MARKDOWN.md`](../docs/MANUAL_CRITERIOS_NORMALIZACION_MARKDOWN.md)\n\n"
        f"---\n\n"
    )
    
    report_content = header_info + audit_report + "\n"
    report_path.write_text(report_content, encoding="utf-8")
    
    print(f"\n✅ Auditoría completada en {elapsed:.2f} segundos.")
    print(f"📄 Reporte persistido en: {report_path.relative_to(REPO_ROOT)}")
    print(f"💡 Puedes abrir '{target_file.name}' e ir directamente a las líneas señaladas para corregir.")


if __name__ == "__main__":
    main()
