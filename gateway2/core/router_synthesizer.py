"""
gateway2.core.router_synthesizer - Despachador RAG Autónomo y Orquestador de Tools (Patrón Router-Synthesizer).
Implementa Ley 1 (Modularización Estricta), Ley 2 (Causa Raíz), Ley 3 (Mínimo Blast Radius),
Ley 4 (Integridad en Cascada RAG) y Ley 5 (Resiliencia Operativa ASD-STE100).

Permite orquestar consultas multi-hop (RAG documental, búsqueda web, consulta de clima, generación de PDFs)
mediante el SLM Evaluador/Router (:18300) para motores principales de inferencia que no soportan Tool Calling nativo (ej. RWKV-7, modelos lineales).
"""

import os
import sys
import re
import json
import time
import uuid
import unicodedata
import asyncio
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

import rag_engine
from gateway2.core.database import get_db

# Parámetros de Configuración del Despachador
EVALUATOR_PORT = int(os.getenv("EVALUATOR_BACKEND_PORT", "18300"))
MASTER_KEY = os.getenv("API_KEY", "")
EVALUATOR_ALIAS = os.getenv("EVALUATOR_ALIAS", "TwIL-LM3-Pro.Q4_K_M")
MAX_HOPS_DEFAULT = int(os.getenv("GATEWAY_DISPATCHER_MAX_HOPS", "3"))
MAX_EVIDENCE_CHARS = int(os.getenv("GATEWAY_DISPATCHER_MAX_CHARS", "25000"))

LOCAL_TOOLS = {
    "buscar_en_base_de_conocimiento",
    "leer_documento_completo",
    "obtener_estructura_documento",
    "obtener_indice_biblioteca",
    "buscar_en_internet",
    "web_search",
    "internet_search",
    "generate_pdf_document",
    "generate_pdf",
    "get_current_weather",
    "get_weather_forecast",
    "consultar_clima",
}


def _format_tool_catalog(tools: List[Dict[str, Any]]) -> str:
    """
    Convierte la lista dinámica de tools de OpenAI recibidas de Open-WebUI
    en una descripción compacta y estructurada para el prompt del SLM Router.
    """
    if not tools:
        return "No hay herramientas disponibles."

    catalog_lines = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        fn = t.get("function", {}) if "function" in t else t
        name = fn.get("name", "").strip()
        if not name:
            continue
        desc = (fn.get("description", "") or "").strip().split("\n")[0]
        params = fn.get("parameters", {})
        props = params.get("properties", {}) if isinstance(params, dict) else {}
        param_list = []
        for p_name, p_info in props.items():
            p_type = p_info.get("type", "any") if isinstance(p_info, dict) else "any"
            param_list.append(f"{p_name}: {p_type}")
        sig = f"- {name}({', '.join(param_list)}): {desc}"
        catalog_lines.append(sig)

    return "\n".join(catalog_lines)


def _build_planner_prompt(tool_catalog: str) -> str:
    return f"""Eres un planificador lógico de herramientas (Router-Synthesizer).
Dada la consulta del usuario, el historial reciente y el catálogo de herramientas disponibles, decide si la consulta requiere ejecutar herramientas (RAG documental, búsqueda web en internet, reporte de clima, generación de PDF, consulta de inventario u otras).

Reglas de decisión deterministas:
1. CONSULTAS CONVERSACIONALES: Si es un saludo, agradecimiento o charla informal que no requiere datos externos ni archivos, responde "requiere_herramientas": false y "acciones": [].
2. DERECHO Y NORMATIVA: Para preguntas sobre doctrina, leyes, tratados, códigos o conceptos jurídicos/técnicos, la herramienta obligatoria de primer paso es SIEMPRE 'buscar_en_base_de_conocimiento' con términos de búsqueda semánticos precisos. NO llames a 'obtener_indice_biblioteca' salvo que el usuario pida explícitamente ver el índice o catálogo general de obras.
3. CLIMA Y PRONÓSTICO: Si el usuario pregunta por el clima o pronóstico y no menciona explícitamente una ciudad o país, la ubicación por defecto del sistema es SIEMPRE "Buenos Aires", país "AR". Queda TERMINANTEMENTE PROHIBIDO asumir ciudades extranjeras como Bogotá, México o Madrid si el usuario no las mencionó expresamente. Usa 'get_current_weather' (hoy) o 'get_weather_forecast' (próximos días).
4. NOTICIAS Y HECHOS EN VIVO: Si el usuario pregunta por noticias recientes, cotizaciones o eventos actuales, selecciona 'buscar_en_internet' formulando una consulta precisa.
5. GENERACIÓN DE PDF: Si el usuario pide generar o pasar a PDF ("pasamelo en PDF", "generar pdf", "exportar a pdf"), selecciona 'generate_pdf_document' y redacta en el parámetro "title" un título formal y específico de 3 a 6 palabras sobre la materia del texto previo a exportar (ej: "Protección Jurídica de la Vida Humana"). Queda PROHIBIDO usar títulos genéricos como "Título representativo del contenido previo" o "Documento Oficial". No vuelques el texto extenso en los parámetros.
6. INVENTARIO, EQUIPOS Y OTRAS HERRAMIENTAS DEL CATÁLOGO: Si el usuario pregunta por datos de un equipo, número de serie, ítem, stock o activo y existe una herramienta específica en el catálogo (ej: 'buscar_item'), selecciona esa herramienta pasando los nombres de parámetros exactos definidos en su firma.

Debes responder EXCLUSIVAMENTE un objeto JSON válido con esta estructura:
{{
  "requiere_herramientas": true o false,
  "plan": "Explicación concisa en una frase",
  "acciones": [
     {{"herramienta": "nombre_exacto", "parametros": {{"param": "valor"}}}}
  ]
}}

Herramientas disponibles:
{tool_catalog}
"""


def _build_router_prompt(tool_catalog: str) -> str:
    return f"""Eres un evaluador y enrutador lógico estricto (Router-Synthesizer).
Analiza la consulta del usuario frente a la evidencia/resultados recopilados hasta el momento.
Tu tarea es decidir si la evidencia ya es suficiente para responder de forma fundada y completa o si hace falta una acción complementaria.

Reglas de evaluación:
1. Si los datos meteorológicos, los resultados de búsqueda web, los datos de inventario/equipos válidos o la confirmación de compilación de PDF ya están disponibles en la evidencia (sin errores ni avisos de ítem inexistente), dictamina inmediatamente "suficiente": true y "siguiente_accion": null. Si una consulta de inventario/ítem devuelve lista vacía, error o informa que el número de serie no existe, dictamina "suficiente": false, "motivo": "No se encontraron registros para el equipo o número de serie consultado", "siguiente_accion": null.
2. Si se consultó la base documental y existe al menos una sección o fragmento doctrinal/normativo que trate sobre la materia de fondo consultada (ej: bienes jurídicos protegidos, vida humana, delitos contra las personas, aunque emplee lenguaje dogmático y no las palabras coloquiales exactas de la pregunta), dictamina inmediatamente "suficiente": true y "siguiente_accion": null.
3. REFORMULACIÓN Y PROFUNDIZACIÓN MULTI-HOP: Si los fragmentos recuperados en la primera búsqueda son meros sumarios de índice (ej: dicen "ÍNDICE GENERAL"), artículos truncados o normas tangenciales (ej: Defensa del Consumidor cuando se pregunta por Derecho Penal/Constitucional), NO dictamines "siguiente_accion": null:
   - Si una fuente recuperada menciona en su texto un parágrafo o sección relevante (ej: "§ 6. Bienes jurídicos protegidos" en doc_id "6ada6fb0191007da2b3f4583"), propone como "siguiente_accion" invocar "leer_documento_completo" con ese "doc_id" y esa "seccion".
   - O bien propone como "siguiente_accion" una nueva búsqueda en "buscar_en_base_de_conocimiento" reformulando la consulta con 3 a 4 palabras clave nucleares y directas (ej: "bienes juridicos protegidos vida humana").
4. PUENTE COGNITIVO PARA ÍNDICES Y CATÁLOGOS: Si la evidencia actual consiste únicamente en un catálogo o índice de biblioteca ('obtener_indice_biblioteca') o en una estructura ('obtener_estructura_documento') y la consulta del usuario requiere una respuesta sustantiva (doctrina, artículos, conceptos, penas), la evidencia es INSUFICIENTE para responder de fondo, pero las obras pertinentes SÍ existen en la biblioteca. Queda TERMINANTEMENTE PROHIBIDO dictaminar 'siguiente_accion': null en este caso. Debes dictaminar "suficiente": false y proponer de inmediato como "siguiente_accion" una búsqueda de contenido sustantivo con 'buscar_en_base_de_conocimiento' o la lectura con 'leer_documento_completo'.
5. Solo si tras reformular o profundizar la información definitivamente no existe en las fuentes oficiales, dictamina "suficiente": false, "motivo": "Ausencia de normativa o registros en fuentes oficiales", "siguiente_accion": null.

Debes responder EXCLUSIVAMENTE un objeto JSON válido con esta estructura:
{{
  "suficiente": true o false,
  "motivo": "Explicación concisa en una frase",
  "siguiente_accion": {{"herramienta": "nombre_herramienta", "parametros": {{"param": "valor"}}}} o null si es suficiente o si la información no existe
}}

Herramientas disponibles si falta información:
{tool_catalog}
"""


def _call_router_slm(messages: List[Dict[str, str]], timeout: float = 8.5) -> Optional[Dict[str, Any]]:
    """Invoca al SLM Router (:18300) con reasoning_effort='none' para latencia ultrarrápida."""
    url = f"http://127.0.0.1:{EVALUATOR_PORT}/v1/chat/completions"
    payload = {
        "model": EVALUATOR_ALIAS,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 700,
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"}
    }

    req_data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if MASTER_KEY:
        headers["Authorization"] = f"Bearer {MASTER_KEY}"

    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return json.loads(content.strip())
    except Exception as exc:
        print(f"⚠️ [Router-Synthesizer] Error comunicando con SLM Router (:{EVALUATOR_PORT}): {exc}", file=sys.stderr, flush=True)
    return None


def _normalize_tool_action(act: Any) -> Tuple[str, Dict[str, Any]]:
    """
    Extrae el nombre de la herramienta y sus parámetros con tolerancia semántica
    ante variaciones de esquema producidas por distintos SLMs (Phi-4, Qwen, TwIL).
    """
    if isinstance(act, str):
        return act.strip(), {}
    if not isinstance(act, dict):
        return "", {}

    # Soporte para variantes de clave de herramienta
    tool_name = (
        act.get("herramienta")
        or act.get("tool")
        or act.get("name")
        or act.get("action")
        or act.get("function")
        or ""
    )
    if isinstance(tool_name, dict):
        tool_name = tool_name.get("name") or tool_name.get("herramienta") or ""
    tool_name = str(tool_name).strip()

    # Soporte para variantes de clave de parámetros
    raw_params = (
        act.get("parametros")
        or act.get("parameters")
        or act.get("arguments")
        or act.get("args")
        or act.get("params")
        or {}
    )
    if isinstance(raw_params, str):
        try:
            parsed = json.loads(raw_params)
            params = parsed if isinstance(parsed, dict) else {}
        except Exception:
            params = {}
    elif isinstance(raw_params, dict):
        params = raw_params
    else:
        params = {}

    return tool_name, params


def _coerce_external_tool_params(
    tool_name: str,
    params: Dict[str, Any],
    tools: List[Dict[str, Any]],
    clean_user_text: str
) -> Dict[str, Any]:
    """
    Normaliza los parámetros para herramientas externas alojadas en Open-WebUI (ej: buscar_item),
    mapeando claves genéricas del SLM al nombre exacto requerido por el JSON Schema de la herramienta.
    """
    if not isinstance(params, dict):
        params = {}
    if not tools:
        return params

    target_schema = None
    for t in tools:
        if not isinstance(t, dict):
            continue
        fn = t.get("function", {}) if "function" in t else t
        if (fn.get("name") or "").strip() == tool_name:
            target_schema = fn.get("parameters", {})
            break

    if not isinstance(target_schema, dict):
        return params

    props = target_schema.get("properties", {})
    if not isinstance(props, dict) or not props:
        return params

    required_keys = target_schema.get("required") or list(props.keys())
    # Si todos los parámetros requeridos ya están presentes con valor no vacío, conservar
    if all(k in params and params[k] not in (None, "") for k in required_keys):
        return {k: v for k, v in params.items() if k in props}

    # Extraer candidato de texto desde claves genéricas del SLM o desde la consulta del usuario
    candidate_val = ""
    for v in params.values():
        if isinstance(v, (str, int, float)) and str(v).strip():
            candidate_val = str(v).strip()
            break

    if not candidate_val:
        # Si la consulta contiene un código/serie alfanumérico largo (ej: 2150087225AGRC018431), priorizarlo
        serial_match = re.search(r"\b([A-Za-z0-9\-]{6,})\b", clean_user_text)
        if serial_match and any(ch.isdigit() for ch in serial_match.group(1)):
            candidate_val = serial_match.group(1)
        else:
            candidate_val = clean_user_text.strip()

    coerced = {k: v for k, v in params.items() if k in props and v not in (None, "")}
    for req_k in required_keys:
        if req_k not in coerced and req_k in props:
            coerced[req_k] = candidate_val

    return coerced if coerced else params


def _deduce_pdf_title(markdown_content: str, messages: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Deduce un título descriptivo limpio cuando el SLM envía un placeholder o título vacío.
    """
    placeholder_headers = {
        "respuesta oficial", "resumen", "conclusion", "conclusión",
        "introduccion", "introducción", "informe ejecutivo", "documento oficial"
    }
    # 1. Buscar primer encabezado Markdown informativo en el contenido
    for line in (markdown_content or "").split("\n"):
        clean_line = line.strip()
        if clean_line.startswith("#"):
            cand = clean_line.lstrip("#* ").strip().rstrip(":")
            if cand and cand.lower() not in placeholder_headers and len(cand) >= 4:
                return cand[:75]

    # 2. Buscar la consulta sustantiva previa del usuario en el historial
    prior_user_q = ""
    if messages and isinstance(messages, list):
        # Recorrer hacia atrás buscando la pregunta anterior a la orden de "pasamelo en PDF"
        found_current_pdf_req = False
        for m in reversed(messages):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                txt = m["content"].strip()
                if "[CONSULTA ACTUAL DEL USUARIO]:" in txt:
                    txt = txt.split("[CONSULTA ACTUAL DEL USUARIO]:", 1)[1].strip()
                txt = re.sub(r"\[DIRECTIVA DE CONTROL.*?$", "", txt, flags=re.DOTALL).strip()
                txt = re.sub(r"<contexto_verificado>.*?</contexto_verificado>", "", txt, flags=re.DOTALL).strip()
                txt = re.sub(r"\[INSTRUCCIÓN AL ASISTENTE.*?$", "", txt, flags=re.DOTALL).strip()
                if not found_current_pdf_req and re.search(r"\bpdf\b", txt, re.IGNORECASE) and len(txt) < 60:
                    found_current_pdf_req = True
                    continue
                if txt and not re.search(r"\bpdf\b", txt, re.IGNORECASE):
                    prior_user_q = txt
                    break

    # Extraer primer concepto destacado en negrita del texto a exportar
    bold_match = re.search(r"\*\*([^*:\n]{3,45})\*\*", (markdown_content or "")[:350])
    bold_concept = bold_match.group(1).strip() if bold_match else ""

    if prior_user_q:
        clean_q = re.sub(r"^[¿\s]*(?:cu[aá]l(?:es)?\s+es\s+(?:el|la)|qu[eé]\s+es\s+(?:el|la)?|mostrame\s+(?:el|la|los|las)?|explicame\s+)\s*", "", prior_user_q, flags=re.IGNORECASE)
        clean_q = clean_q.rstrip("?.! ").strip()
        # Acotar en cláusula subordinada larga ("que, según...")
        short_q = re.split(r"\s+que[\s,]+", clean_q, maxsplit=1)[0].strip()
        base_topic = (short_q if len(short_q) >= 8 else clean_q[:55]).strip()
        if base_topic:
            base_title = base_topic[0].upper() + base_topic[1:]
            if bold_concept and bold_concept.lower() not in base_title.lower():
                return f"{base_title}: {bold_concept.title()}"[:75]
            return base_title[:75]

    if bold_concept:
        return f"Informe sobre {bold_concept.title()}"[:75]

    return "Informe Técnico y Doctrinario"


def _execute_local_tool(
    action_name: str,
    params: Dict[str, Any],
    target_table: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    user_query: Optional[str] = None
) -> Tuple[str, str]:
    """
    Ejecuta una herramienta de forma desacoplada y devuelve (etiqueta, contenido_markdown).
    Soporta:
    - RAG Documental (LanceDB)
    - Búsqueda Web en tiempo real (Ollama Web Search)
    - Generación y descarga de archivos PDF (pdf_engine)
    - Consulta meteorológica (OpenWeatherMap / Web Search Fallback)
    """
    action_name = (action_name or "").strip()
    if not isinstance(params, dict):
        params = {}

    try:
        # --- 1. HERRAMIENTAS RAG DOCUMENTAL (LanceDB) ---
        if action_name == "buscar_en_base_de_conocimiento":
            consulta = params.get("consulta") or params.get("query") or ""
            tema = params.get("tema") or params.get("dominio")
            top_k = max(5, int(params.get("top_k") or 5))
            results = rag_engine.search_knowledge_base(
                query=consulta,
                tema=tema,
                top_k=top_k,
                table_name=target_table
            )
            formatted = rag_engine.format_rag_context_for_llm(results)
            return f"Búsqueda Documental: '{consulta}'", formatted

        elif action_name == "leer_documento_completo":
            doc_id = params.get("doc_id", "")
            seccion = params.get("seccion") or params.get("section")
            parte = int(params.get("parte", 1))
            res = rag_engine.get_document_full_content(
                doc_id=doc_id,
                seccion=seccion,
                parte=parte,
                table_name=target_table
            )
            content = res.get("content", "")
            return f"Lectura Documento: {doc_id} ({seccion or 'íntegro'})", content

        elif action_name == "obtener_estructura_documento":
            doc_id = params.get("doc_id", "")
            filtro = params.get("filtro") or params.get("filter")
            res = rag_engine.get_document_structure(
                doc_id=doc_id,
                filtro=filtro,
                table_name=target_table
            )
            content = res.get("content", "")
            return f"GPS Estructura: {doc_id}", content

        elif action_name == "obtener_indice_biblioteca":
            solo_vigentes = bool(params.get("solo_vigentes", True))
            tema = params.get("tema") or params.get("dominio")
            res = rag_engine.get_library_index(
                solo_vigentes=solo_vigentes,
                tema=tema,
                table_name=target_table
            )
            content = res.get("content", "")
            return "Índice Biblioteca", content

        # --- 2. HERRAMIENTAS DE BÚSQUEDA WEB EN VIVO ---
        elif action_name in ["buscar_en_internet", "web_search", "internet_search"]:
            consulta = params.get("consulta") or params.get("query") or params.get("q") or ""
            max_res = int(params.get("max_resultados") or params.get("max_results") or 3)
            from gateway2.tools.web_search import perform_ollama_web_search
            results = asyncio.run(perform_ollama_web_search(consulta, max_results=max_res))
            if results:
                snippets = []
                for idx, r in enumerate(results, 1):
                    snippets.append(f"[{idx}] {r.get('title')}\nURL: {r.get('url')}\nContenido: {r.get('content')}")
                formatted = "[INFORMACIÓN DE BÚSQUEDA WEB EN TIEMPO REAL]:\n\n" + "\n\n".join(snippets)
                return f"Búsqueda Web: '{consulta}'", formatted
            else:
                return f"Búsqueda Web: '{consulta}'", "No se encontraron resultados web relevantes."

        # --- 3. GENERACIÓN DE ARCHIVOS PDF ---
        elif action_name in ["generate_pdf_document", "generate_pdf"]:
            # Localizar el último mensaje del asistente en el historial para exportar su contenido real
            prior_assistant_content = ""
            if messages:
                for m in reversed(messages):
                    if m.get("role") == "assistant" and m.get("content"):
                        prior_assistant_content = m["content"].strip()
                        break

            title = (params.get("title") or "").strip()
            raw_filename = params.get("filename")
            markdown_content = (params.get("markdown_content") or params.get("content") or params.get("contenido") or "").strip()

            # Si el contenido en params es un placeholder corto (<150 caracteres) o vacío,
            # usar siempre el contenido completo del mensaje anterior del asistente
            if len(markdown_content) < 150 and prior_assistant_content:
                markdown_content = prior_assistant_content

            if not markdown_content:
                markdown_content = prior_assistant_content or f"# {title or 'Documento Oficial'}\n\nDocumento exportado sin contenido previo."

            # Deducir un título descriptivo si viene vacío o con palabras placeholder genéricas
            placeholder_titles = [
                "documento oficial", "consulta de normativa", "pdf", "resumen",
                "documento", "nombre_del_pdf", "título representativo",
                "titulo representativo", "contenido previo", "informe ejecutivo",
                "sin título", "sin titulo", "exportar", "pasamelo"
            ]
            if not title or any(p in title.lower() for p in placeholder_titles):
                title = _deduce_pdf_title(markdown_content, messages)

            # Sanitizar filename si es un placeholder genérico y normalizar a ASCII limpio
            clean_filename_param = raw_filename
            if not clean_filename_param or any(p in clean_filename_param.lower() for p in placeholder_titles):
                ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
                slug = re.sub(r"[^\w\-\.]", "_", ascii_title.lower()).strip("._")
                slug = re.sub(r"_+", "_", slug) or "documento_oficial"
                clean_filename_param = f"{slug[:45]}.pdf"

            from pdf_engine import create_pdf_from_markdown
            pdf_res = create_pdf_from_markdown(
                title=title,
                markdown_content=markdown_content,
                filename=clean_filename_param
            )
            download_url = pdf_res.get("download_url", "")
            final_filename = pdf_res.get("filename", "documento.pdf")
            page_count = pdf_res.get("pages", 1)
            size_kb = pdf_res.get("size_kb", 0)

            formatted_card = (
                f"✅ Archivo PDF compilado exitosamente.\n\n"
                f"Enlace de descarga oficial para el usuario:\n"
                f"[📥 Descargar {final_filename}]({download_url})\n\n"
                f"Detalles del documento generado:\n"
                f"* Archivo: `{final_filename}` ({page_count} páginas, {size_kb} KB)\n"
                f"* Título: {title}\n"
                f"* Resumen del contenido: Se exportó fielmente el informe del turno anterior ('{title}')."
            )
            return f"Generación PDF: '{final_filename}'", formatted_card

        # --- 4. CONSULTA DE CLIMA / METEOROLOGÍA ---
        elif action_name in ["get_current_weather", "get_weather_forecast", "consultar_clima"]:
            raw_city = (params.get("city") or params.get("ciudad") or "").strip()
            raw_country = (params.get("country_code") or params.get("pais") or "").strip()

            user_text = (user_query or "").lower()
            if not raw_city or (raw_city.lower() not in user_text and raw_city.lower() in ["bogota", "bogotá", "mexico", "madrid", "colombia"]):
                city = "Buenos Aires"
                country = "AR"
            else:
                city = raw_city
                country = raw_country or ("AR" if city.lower() in ["buenos aires", "san nicolas", "cordoba", "rosario", "mendoza"] else None)

            openweather_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
            weather_success = False
            weather_output = ""
            if openweather_key:
                try:
                    from tools.openwebui_weather_tool import Tools as WeatherTools
                    wt = WeatherTools()
                    wt.valves.OPENWEATHER_API_KEY = openweather_key
                    if action_name == "get_weather_forecast":
                        weather_output = wt.get_weather_forecast(city, country)
                    else:
                        weather_output = wt.get_current_weather(city, country)
                    if not weather_output.startswith("Error"):
                        weather_success = True
                except Exception as we_err:
                    print(f"⚠️ Error ejecutando OpenWeather: {we_err}", file=sys.stderr, flush=True)

            # Fallback Resiliente: Búsqueda Web de Clima en Vivo si OpenWeather no está disponible
            if not weather_success:
                from gateway2.tools.web_search import perform_ollama_web_search
                q_weather = f"pronostico del tiempo clima {city} {country or ''} hoy reporte meteorologico"
                w_results = asyncio.run(perform_ollama_web_search(q_weather, max_results=3))
                if w_results:
                    snippets = []
                    for idx, r in enumerate(w_results, 1):
                        snippets.append(f"[{idx}] {r.get('title')}\nURL: {r.get('url')}\n{r.get('content')}")
                    weather_output = f"[REPORTE METEOROLÓGICO WEB EN TIEMPO REAL PARA {city.upper()}]:\n\n" + "\n\n".join(snippets)
                else:
                    weather_output = f"No se pudo obtener información meteorológica actualizada para {city}."

            return f"Clima: {city} ({country or 'Local'})", weather_output

        else:
            return f"Herramienta no implementada: {action_name}", f"La herramienta '{action_name}' no tiene controlador local registrado."

    except Exception as err:
        return f"Error ejecutando {action_name}", f"Error: {err}"


async def process_router_synthesizer(
    data: Dict[str, Any],
    key_doc: Optional[Dict[str, Any]] = None,
    target_table: Optional[str] = None
) -> Dict[str, Any]:
    """
    Orquestador principal del patrón Router-Synthesizer con Evaluación de Suficiencia (CRAG).
    1. Detecta si la consulta califica para ejecución agéntica de tools.
    2. Ejecuta el bucle cognitivo multi-hop en el evaluador (:18300).
    3. Evalúa suficiencia probatoria y presupuesto útil de evidencia.
    4. Inyecta la evidencia o directiva de abstención honesta en <contexto_verificado>.
    5. Retira las tools del payload para el LLM principal (:18100).
    """
    messages = data.get("messages")
    if not messages or not isinstance(messages, list):
        return data

    # Si no tiene tools definidas, no interceptar (flujo directo)
    tools = data.get("tools")
    if not tools:
        return data

    # Extraer la última consulta del usuario
    user_msg_idx = -1
    user_query = ""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            user_msg_idx = i
            raw_content = messages[i].get("content")
            if isinstance(raw_content, str):
                user_query = raw_content.strip()
            elif isinstance(raw_content, list):
                text_parts = [p.get("text", "") for p in raw_content if isinstance(p, dict) and p.get("type") == "text"]
                user_query = " ".join(text_parts).strip()
            break

    if not user_query or user_msg_idx == -1:
        return data

    # Extraer consulta limpia despojando inyecciones de middleware previo para decisiones lógicas puras (Ley 4)
    clean_user_text = user_query
    if clean_user_text.startswith("[CONSULTA ACTUAL DEL USUARIO]:"):
        clean_user_text = clean_user_text[len("[CONSULTA ACTUAL DEL USUARIO]:"):].strip()
    clean_user_text = re.sub(r'\[DIRECTIVA DE CONTROL.*?$', '', clean_user_text, flags=re.DOTALL).strip()
    clean_user_text = re.sub(r'\[FASE DE INVESTIGACIÓN.*?$', '', clean_user_text, flags=re.DOTALL).strip()
    if not clean_user_text:
        clean_user_text = user_query

    print(f"\n🧭 [Router-Synthesizer] Iniciando orquestación de herramientas para: '{clean_user_text[:80]}...'", flush=True)
    t_start = time.time()

    # Resolver tabla de LanceDB si existe perfil
    if not target_table and key_doc and isinstance(key_doc, dict):
        target_table = key_doc.get("rag_table") or key_doc.get("company_profile", {}).get("rag_table")

    # Construir catálogo dinámico de herramientas provistas por Open-WebUI
    tool_catalog = _format_tool_catalog(tools)
    planner_prompt = _build_planner_prompt(tool_catalog)
    router_prompt = _build_router_prompt(tool_catalog)
    available_tool_names = {
        ((t.get("function", {}) if "function" in t else t).get("name") or "").strip()
        for t in tools if isinstance(t, dict)
    }

    evidence_blocks: List[str] = []
    executed_tools: List[str] = []
    is_sufficient = False
    eval_reason = ""

    # --- FASE B: Recepción de resultados de herramientas externas ejecutadas por Open-WebUI (role == "tool") ---
    trailing_tool_msgs = [m for m in messages[user_msg_idx + 1:] if isinstance(m, dict) and m.get("role") == "tool"]
    if trailing_tool_msgs:
        print(f"🔌 [Router-Synthesizer] Procesando {len(trailing_tool_msgs)} resultado(s) de herramienta externa devueltos por Open-WebUI...", flush=True)
        for tm in trailing_tool_msgs:
            raw_t_content = str(tm.get("content") or "").strip()
            # Limpiar pies de anclaje inyectados previamente por alignment_engine
            raw_t_content = re.sub(r"📌\s*\[(?:RECORDATORIO DE FOCO ACTIVO|ACTIVE TASK FOCUS).*?$", "", raw_t_content, flags=re.DOTALL).strip()
            t_name = str(tm.get("name") or "herramienta_externa").strip()
            executed_tools.append(t_name)
            if raw_t_content:
                evidence_blocks.append(f"--- Resultado Herramienta ({t_name}) ---\n{raw_t_content}")

        # Podar mensajes de tool_calls/tool para que el sintetizador lineal (:18100) reciba estructura limpia user-final
        del messages[user_msg_idx + 1:]

        total_evidence = "\n\n".join(evidence_blocks)
        empty_or_not_found = bool(
            not total_evidence.strip()
            or re.search(
                r"\b(?:no\s+se\s+encontr(?:o|aron)|sin\s+resultados|no\s+existe(?:n)?|not\s+found|404|error\s+al\s+consultar|no\s+registrado)\b",
                total_evidence,
                re.IGNORECASE
            )
            or total_evidence.strip().endswith("[]")
        )
        if empty_or_not_found:
            is_sufficient = False
            eval_reason = "No se encontraron registros coincidentes en el sistema para el ítem o número de serie consultado."
        else:
            eval_resp = await asyncio.to_thread(
                _call_router_slm,
                [
                    {"role": "system", "content": router_prompt},
                    {"role": "user", "content": f"CONSULTA DEL USUARIO:\n{clean_user_text}\n\nEVIDENCIA Y RESULTADOS ACTUALES:\n{total_evidence[:16000]}"}
                ]
            )
            if eval_resp and isinstance(eval_resp, dict):
                is_sufficient = bool(eval_resp.get("suficiente", True))
                eval_reason = eval_resp.get("motivo", "")
            else:
                is_sufficient = True
                eval_reason = "Datos recuperados de herramienta externa."
    else:
        is_explicit_pdf = bool(re.search(
            r"\b(?:pdf|pasamelo\s+en\s+pdf|generar\s+pdf|exportar\s+(?:a\s+)?pdf|crear\s+pdf|en\s+pdf|descargar\s+pdf|bajar\s+pdf|hacer\s+pdf)\b",
            clean_user_text,
            re.IGNORECASE
        ))

        planner_user_content = f"CONSULTA DEL USUARIO:\n{clean_user_text}"
        if is_explicit_pdf:
            for m in reversed(messages[:user_msg_idx]):
                if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content"):
                    snippet = str(m["content"]).strip()[:350]
                    planner_user_content += f"\n\n[EXTRACTO DEL TEXTO PREVIO A EXPORTAR]:\n{snippet}"
                    break

        # --- PASO 1: Planificación Inicial (Hop 0) ---
        plan_resp = await asyncio.to_thread(
            _call_router_slm,
            [
                {"role": "system", "content": planner_prompt},
                {"role": "user", "content": planner_user_content}
            ]
        )

        requires_tools = False
        if plan_resp and isinstance(plan_resp, dict):
            requires_tools = bool(
                plan_resp.get("requiere_herramientas")
                or plan_resp.get("requiere_rag")
                or (plan_resp.get("acciones") and len(plan_resp["acciones"]) > 0)
            )

        if is_explicit_pdf:
            requires_tools = True

        if not requires_tools:
            print("🧭 [Router-Synthesizer] Consulta conversacional/general. Omitiendo herramientas y sintetizando en lenguaje natural puro.", flush=True)
            data.pop("tools", None)
            data.pop("tool_choice", None)
            return data

        raw_actions = plan_resp.get("acciones") if (plan_resp and isinstance(plan_resp, dict)) else []
        initial_actions = raw_actions if isinstance(raw_actions, list) and raw_actions else []

        if is_explicit_pdf:
            has_pdf_act = any(_normalize_tool_action(a)[0] in ["generate_pdf_document", "generate_pdf"] for a in initial_actions)
            if not has_pdf_act:
                initial_actions = [{"herramienta": "generate_pdf_document", "parametros": {"title": "Documento Oficial"}}]

        if not initial_actions:
            initial_actions = [{"herramienta": "buscar_en_base_de_conocimiento", "parametros": {"consulta": clean_user_text}}]

        executed_signatures: set = set()
        executed_search_queries: set = set()
        max_hops = int(os.getenv("GATEWAY_DISPATCHER_MAX_HOPS", str(MAX_HOPS_DEFAULT)))

        # --- PASO 2: Bucle Agéntico Multi-Hop ---
        current_actions = initial_actions
        for hop in range(1, max_hops + 1):
            print(f"🧭 [Router-Synthesizer] Hop {hop}/{max_hops}: Ejecutando {len(current_actions)} acción/es...", flush=True)
            hop_blocks: List[str] = []

            for act in current_actions:
                tool_name, params = _normalize_tool_action(act)
                if not tool_name and is_explicit_pdf:
                    tool_name = "generate_pdf_document"
                if not tool_name:
                    continue

                # --- FASE A: Si la herramienta es externa (alojada en Open-WebUI, ej. buscar_item), delegar mediante tool_calls ---
                if tool_name not in LOCAL_TOOLS and tool_name in available_tool_names:
                    coerced_params = _coerce_external_tool_params(tool_name, params, tools, clean_user_text)
                    call_id = f"call_{uuid.uuid4().hex[:12]}"
                    print(f"🔌 [Router-Synthesizer] Delegando herramienta externa '{tool_name}' a Open-WebUI con params={coerced_params}.", flush=True)
                    data["_delegated_tool_calls"] = [{
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(coerced_params, ensure_ascii=False)
                        }
                    }]
                    return data

                act_sig = f"{tool_name}:{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
                executed_signatures.add(act_sig)
                if tool_name == "buscar_en_base_de_conocimiento":
                    q_val = (params.get("consulta") or params.get("query") or "").strip().lower()
                    if q_val:
                        executed_search_queries.add(q_val)

                label, content = await asyncio.to_thread(
                    _execute_local_tool,
                    tool_name,
                    params,
                    target_table,
                    messages,
                    user_query
                )
                if content:
                    block_str = f"--- {label} ---\n{content}"
                    hop_blocks.append(block_str)
                    evidence_blocks.append(block_str)
                    executed_tools.append(tool_name)

            # Consolidar evidencia actual
            total_evidence = "\n\n".join(evidence_blocks)
            if len(total_evidence) > MAX_EVIDENCE_CHARS:
                total_evidence = total_evidence[:MAX_EVIDENCE_CHARS] + "\n\n[... Evidencia truncada por límite de contexto ...]"

            # Si ya se ejecutó un PDF, no requiere más saltos
            if any(t in ["generate_pdf_document", "generate_pdf"] for t in executed_tools):
                print(f"✅ [Router-Synthesizer] Acción PDF completada en Hop {hop}.", flush=True)
                is_sufficient = True
                eval_reason = "Archivo PDF generado y almacenado en disco."
                break

            # Evaluar suficiencia documental con el SLM Router (:18300)
            eval_resp = await asyncio.to_thread(
                _call_router_slm,
                [
                    {"role": "system", "content": router_prompt},
                    {"role": "user", "content": f"CONSULTA DEL USUARIO:\n{clean_user_text}\n\nEVIDENCIA Y RESULTADOS ACTUALES:\n{total_evidence[:16000]}"}
                ]
            )

            if not eval_resp:
                print("🧭 [Router-Synthesizer] Sin respuesta del evaluador. Finalizando bucle con evidencia actual.", flush=True)
                break

            is_sufficient = bool(eval_resp.get("suficiente", False))
            eval_reason = eval_resp.get("motivo", "")
            next_action = eval_resp.get("siguiente_accion")

            print(f"⚖️ [Router-Synthesizer] Hop {hop}: suficiente={is_sufficient} | Motivo: {eval_reason}", flush=True)

            # Si este salto posterior (hop > 1) logró suficiencia tras saltos previos insuficientes,
            # retener únicamente la evidencia limpia del salto exitoso para eliminar fragmentos descartados
            if is_sufficient and hop > 1 and hop_blocks:
                evidence_blocks = list(hop_blocks)

            # Verificar si la acción propuesta por el evaluador ya fue ejecutada (o si repite la misma consulta RAG)
            if not is_sufficient and next_action:
                cand_tool, cand_params = _normalize_tool_action(next_action)
                cand_sig = f"{cand_tool}:{json.dumps(cand_params, sort_keys=True, ensure_ascii=False)}"
                cand_q = (cand_params.get("consulta") or cand_params.get("query") or "").strip().lower()
                already_searched_same_q = (
                    cand_tool == "buscar_en_base_de_conocimiento"
                    and "buscar_en_base_de_conocimiento" in executed_tools
                    and (not cand_q or cand_q in executed_search_queries or cand_q in clean_user_text.lower())
                )
                if not cand_tool or cand_sig in executed_signatures or already_searched_same_q:
                    next_action = None

            # Salvaguarda determinista de Puente Cognitivo y Profundización Multi-Hop (Ley 2 / Ley 4):
            if not is_sufficient and not next_action and hop < max_hops:
                if executed_tools == ["obtener_indice_biblioteca"]:
                    is_catalog_only_query = bool(re.search(r"\b(?:list(?:a|ame|ar)|qu[eé]\s+libros|cat[aá]logo|obras\s+hay|qu[eé]\s+ten[eé]s)\b", clean_user_text, re.IGNORECASE))
                    if not is_catalog_only_query:
                        print("🌉 [Router-Synthesizer] Activando Puente Cognitivo automático: Índice relevado -> Buscando contenido sustantivo con 'buscar_en_base_de_conocimiento'.", flush=True)
                        next_action = {
                            "herramienta": "buscar_en_base_de_conocimiento",
                            "parametros": {"consulta": clean_user_text, "top_k": 5}
                        }
                elif "buscar_en_base_de_conocimiento" in executed_tools and "leer_documento_completo" not in executed_tools:
                    # Si en los fragmentos recuperados apareció un sumario con referencia de parágrafo (§ X. Título) dentro del mismo bloque de fuente, profundizar en esa sección
                    sec_match = re.search(
                        r'\[doc_id:\s*([a-f0-9]{16,32})\](?:(?!--- FUENTE \[).)*?(§\s*\d+\.\s*[A-Za-zÁÉÍÓÚáéíóúñÑ\s,\.\"\-]{4,55}?)(?:\s+\d+\s+[IVXLCDM]+|\s+ÍNDICE|\n|$)',
                        total_evidence,
                        re.DOTALL
                    )
                    if sec_match:
                        found_doc_id = sec_match.group(1).strip()
                        found_sec = sec_match.group(2).strip()
                        print(f"🌉 [Router-Synthesizer] Profundización automática en sumario detectado: doc_id={found_doc_id} | seccion='{found_sec}'.", flush=True)
                        next_action = {
                            "herramienta": "leer_documento_completo",
                            "parametros": {"doc_id": found_doc_id, "seccion": found_sec}
                        }

            if is_sufficient or not next_action:
                print(f"✅ [Router-Synthesizer] Bucle completado en Hop {hop} (suficiente={is_sufficient}).", flush=True)
                break

            # Configurar siguiente acción para el próximo salto si no es suficiente
            n_tool, n_params = _normalize_tool_action(next_action)
            n_sig = f"{n_tool}:{json.dumps(n_params, sort_keys=True, ensure_ascii=False)}"
            if n_tool and n_sig not in executed_signatures:
                current_actions = [{"herramienta": n_tool, "parametros": n_params}]
            else:
                break

    total_time_ms = round((time.time() - t_start) * 1000, 2)
    consolidated_evidence = "\n\n".join(evidence_blocks)
    # Limpiar sugerencias de llamadas a herramientas para el sintetizador final (que opera sin tools)
    clean_evidence_for_synthesis = re.sub(
        r'💡 \[Acción Disponible[^\n]*\n(?:\s*-\s*Para [^\n]*\n)*',
        '',
        consolidated_evidence
    ).strip()

    evidence_tokens = max(1, len(clean_evidence_for_synthesis) // 4)
    print(f"🏁 [Router-Synthesizer] Finalizado en {total_time_ms}ms con {len(executed_tools)} llamadas ({', '.join(executed_tools)}). Evidencia: {len(clean_evidence_for_synthesis):,} chars (~{evidence_tokens} tokens) | Suficiente: {is_sufficient}.", flush=True)

    # --- PASO 3: Ensamblaje del Payload para el Motor de Síntesis (:18100) ---
    data.pop("tools", None)
    data.pop("tool_choice", None)

    is_pdf_generation = any(t in ["generate_pdf_document", "generate_pdf"] for t in executed_tools)
    user_header = f"[CONSULTA ACTUAL DEL USUARIO]:\n{clean_user_text}"

    if is_pdf_generation:
        augmented_user_prompt = (
            f"{user_header}\n\n"
            f"<contexto_verificado>\n"
            f"[RESULTADO DE GENERACIÓN DE ARCHIVO PDF]:\n"
            f"{clean_evidence_for_synthesis}\n"
            f"</contexto_verificado>\n\n"
            f"[INSTRUCCIÓN AL ASISTENTE (GENERACIÓN DE PDF)]:\n"
            f"El archivo PDF ha sido compilado y guardado en disco con el contenido exacto del mensaje previo.\n"
            f"Comunica al usuario que su documento PDF está listo y proporciónale el enlace de descarga oficial en Markdown provisto en <contexto_verificado>.\n"
            f"Queda TERMINANTEMENTE PROHIBIDO inventar normativas, leyes, artículos (ej: Art 1074 CCyCN), resoluciones o citar temas de turnos anteriores (ej: Bogotá o leyes no relacionadas).\n"
            f"Limita tu respuesta a 1 o 2 párrafos claros, profesionales y concluyentes con el enlace de descarga."
        )

    elif not is_sufficient:
        # --- PRESERVACIÓN DE PISO MÍNIMO Y ABSTENCIÓN GUIADA MEA (LEY 4) ---
        print(f"🛡️ [Router-Synthesizer] Activando Directiva de Abstención MEA: Evidencia insuficiente ({eval_reason}).", flush=True)
        # Extraer solo los títulos de las obras vistas para evitar que el modelo entre en bucle copiando bloques '--- FUENTE [X] ---'
        seen_titles = sorted(set(re.findall(r'--- FUENTE \[\d+\]:\s*"([^"]+)"', clean_evidence_for_synthesis)))
        titles_summary = (
            f"Obras inspeccionadas sin resultado concluyente sobre el punto: {', '.join(seen_titles)}."
            if seen_titles else
            "No se localizaron fragmentos específicos que regulen de forma directa la consulta."
        )
        augmented_user_prompt = (
            f"{user_header}\n\n"
            f"<contexto_verificado>\n"
            f"Estado de búsqueda documental: {titles_summary}\n"
            f"Evaluación técnica: {eval_reason}\n"
            f"</contexto_verificado>\n\n"
            f"[INSTRUCCIÓN AL ASISTENTE (ABSTENCIÓN POR INSUFICIENCIA PROBATORIA - MEA)]:\n"
            f"El evaluador deductivo determinó que la evidencia documental disponible es INSUFICIENTE para responder de forma fundada ({eval_reason}).\n"
            f"Conforme al Invariante de Veracidad (Gate 1 del MEA y Ley 4):\n"
            f"1. Declara formal y explícitamente en prosa natural que las fuentes oficiales consultadas no contienen datos suficientes para responder con certeza jurídica o técnica a la consulta.\n"
            f"2. Queda TERMINANTEMENTE PROHIBIDO inventar leyes, artículos, números de decretos o doctrinas no presentes en la evidencia.\n"
            f"3. Queda TERMINANTEMENTE PROHIBIDO copiar, transcribir o enumerar cabeceras de fuentes ('--- FUENTE [X]: ...' o '📜 [EVIDENCIA...'). Redacta únicamente 1 o 2 párrafos sobrios y profesionales."
        )

    else:
        # Síntesis normal con evidencia verificada
        augmented_user_prompt = (
            f"{user_header}\n\n"
            f"<contexto_verificado>\n"
            f"[EVIDENCIA Y RESULTADOS DE HERRAMIENTAS]:\n"
            f"{clean_evidence_for_synthesis}\n"
            f"</contexto_verificado>\n\n"
            f"[INSTRUCCIÓN AL ASISTENTE]:\n"
            f"Responde la consulta del usuario basándote con rigor y fidelidad en los datos provistos en <contexto_verificado>.\n"
            f"Instrucciones de redacción:\n"
            f"1. Fundamenta tu respuesta exclusivamente en los hechos, datos y documentos de <contexto_verificado>.\n"
            f"2. CITACIÓN NOMINAL OBLIGATORIA: Cuando la evidencia incluya el título de una obra doctrinaria, código, ley, parágrafo (§) o el nombre de su autor (ej: 'Derecho Penal Parte Especial', 'Autor: Carlos Creus', '§ 6. Bienes jurídicos protegidos'), menciónalos explícitamente por su nombre en tu prosa (no digas solo 'según la doctrina' de forma anónima).\n"
            f"3. FIDELIDAD LITERAL DE ENTIDADES: Transcribe con exactitud literal los nombres propios de personas, papas, autoridades, números de serie, fechas y cifras tal como figuran en <contexto_verificado>. Queda TERMINANTEMENTE PROHIBIDO sustituir un nombre propio de la evidencia por otro de tu memoria previa (ej: jamás cambies 'Papa León XIV' por 'Papa Francisco').\n"
            f"4. Desarrolla una conclusión directa, estructurada y con cierre claro.\n"
            f"Queda terminantemente prohibido inventar normativas, artículos inexistentes, enlaces simulados o reproducir literalmente las cabeceras técnicas crudas '--- FUENTE [X] ---'.\n"
            f"No menciones etiquetas técnicas como '<contexto_verificado>': redacta tu respuesta de forma directa, profesional y fundada."
        )

    messages[user_msg_idx]["content"] = augmented_user_prompt
    data["messages"] = messages
    return data
