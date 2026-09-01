import os
import sys
import re
import time
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo import MongoClient

from config import get_mongo_uri, MONGO_DB
from gateway.tools.web_search import perform_ollama_web_search

DEFAULT_INVARIANTS_PROMPT = """🏛️ [DIRECTIVAS FUNDAMENTALES Y DEBER DE VERACIDAD (INVARIANTES NO NEGOCIABLES)]
1. PROHIBICIÓN ABSOLUTA DE ENLACES SIMULADOS O FICTICIOS:
   - Jamás inventes URLs, hipervínculos markdown manuales a dominios ficticios (como example.com, test.com) ni redactes mensajes de 'entorno simulado o representativo'.
   - Si el usuario solicita un archivo descargable, reporte formal o resumen en PDF, es MANDATORIO generar el archivo invocando la herramienta formal del sistema. Está estrictamente prohibido simular que el archivo fue creado sin haber emitido la llamada a la tool.
2. FIDELIDAD DOCUMENTAL Y EXHAUSTIVIDAD:
   - Al analizar, sintetizar o explicar documentos operativos, procedimientos técnicos o normativas, procesa la totalidad del contenido relevante.
   - Conserva con exactitud matemática y conceptual las tablas comparativas, las categorías operativas (ej: ASC, ASE, ASG), los tiempos límites y los protocolos de comunicación sin omitir detalles críticos ni aplicar atajos superficiales.
3. RIGOR TÉCNICO Y HONESTIDAD:
   - Si una información no está presente en el contexto o en las herramientas disponibles, decláralo con total transparencia en lugar de suponerla o inventarla."""

DEFAULT_ALIGNMENT_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "inject_temporal": True,
    "inject_invariants": True,
    "invariants_prompt": DEFAULT_INVARIANTS_PROMPT,
    "custom_system_prompt": "",
    "max_response_tokens_cap": 8192,
    "pdf_protocol_enabled": True,
    "doc_reader_protocol_enabled": True
}

cached_alignment_settings: Dict[str, Any] = dict(DEFAULT_ALIGNMENT_SETTINGS)
cached_alignment_lock = asyncio.Lock()


def get_db():
    client = MongoClient(get_mongo_uri(), serverSelectionTimeoutMS=1000)
    return client[MONGO_DB]


def get_current_time_str() -> str:
    """Retorna la fecha y hora local formateada en español."""
    now_local = datetime.now()
    dias_semana = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses_ano = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    dia_nombre = dias_semana[now_local.weekday()]
    mes_nombre = meses_ano[now_local.month - 1]
    return f"Fecha y hora actual: {dia_nombre} {now_local.day} de {mes_nombre} de {now_local.year}, {now_local.strftime('%H:%M:%S')} (Hora local)."


def get_alignment_settings() -> Dict[str, Any]:
    """Retorna la configuración de alineación actual (desde caché en memoria o MongoDB)."""
    global cached_alignment_settings
    if cached_alignment_settings:
        return cached_alignment_settings
    try:
        db = get_db()
        doc = db.alignment_settings.find_one({"_id": "global"})
        if doc:
            settings = dict(DEFAULT_ALIGNMENT_SETTINGS)
            for k in DEFAULT_ALIGNMENT_SETTINGS:
                if k in doc:
                    settings[k] = doc[k]
            cached_alignment_settings = settings
            return settings
    except Exception:
        pass
    return dict(DEFAULT_ALIGNMENT_SETTINGS)


def save_alignment_settings(settings: Dict[str, Any]) -> bool:
    """Guarda la configuración de alineación en MongoDB y actualiza la caché en memoria."""
    global cached_alignment_settings
    try:
        db = get_db()
        update_doc = {"updated_at": time.time()}
        for k in DEFAULT_ALIGNMENT_SETTINGS:
            if k in settings:
                update_doc[k] = settings[k]

        db.alignment_settings.update_one(
            {"_id": "global"},
            {"$set": update_doc},
            upsert=True
        )
        new_cached = dict(DEFAULT_ALIGNMENT_SETTINGS)
        new_cached.update(update_doc)
        cached_alignment_settings = new_cached
        return True
    except Exception as e:
        print(f"⚠️ Error guardando configuración de alineación en MongoDB: {e}", file=sys.stderr, flush=True)
        return False


async def sync_alignment_settings_loop():
    """Lazo en segundo plano para sincronizar la configuración de alineación desde MongoDB cada 10s."""
    global cached_alignment_settings
    print("🛡️ Sincronizador de políticas de alineación (MEA) del Gateway Iniciado.", flush=True)
    while True:
        try:
            db = get_db()
            doc = db.alignment_settings.find_one({"_id": "global"})
            if doc:
                settings = dict(DEFAULT_ALIGNMENT_SETTINGS)
                for k in DEFAULT_ALIGNMENT_SETTINGS:
                    if k in doc:
                        settings[k] = doc[k]
                async with cached_alignment_lock:
                    cached_alignment_settings = settings
            else:
                # Inicializar documento por defecto en MongoDB si no existe
                db.alignment_settings.update_one(
                    {"_id": "global"},
                    {"$setOnInsert": dict(DEFAULT_ALIGNMENT_SETTINGS)},
                    upsert=True
                )
        except Exception as e:
            # Fallback silencioso para no interferir con la inferencia
            pass
        await asyncio.sleep(10)


def get_invariants_system_prompt(settings: Dict[str, Any], has_pdf_tool: bool = False, has_doc_tool: bool = False) -> str:
    """Construye el bloque de invariantes éticos y operativos."""
    blocks = []
    
    if settings.get("inject_invariants", True):
        invariants_text = settings.get("invariants_prompt", DEFAULT_INVARIANTS_PROMPT).strip()
        if invariants_text:
            blocks.append(invariants_text)

    if settings.get("pdf_protocol_enabled", True) and has_pdf_tool:
        blocks.append(
            "\n📄 [PROTOCOLO OBLIGATORIO DE GENERACIÓN DE PDF]:\n"
            "- Cuando el usuario pida un PDF, resumen ejecutivo exportable o informe formal, debes EMITIR LA LLAMADA A LA HERRAMIENTA `generate_pdf_document` con los argumentos `filename`, `title` y `markdown_content`.\n"
            "- NUNCA respondas con un enlace estático inventado en texto sin haber ejecutado la herramienta."
        )

    if settings.get("doc_reader_protocol_enabled", True) and has_doc_tool:
        blocks.append(
            "\n📚 [PROTOCOLO DE LECTURA Y NAVEGACIÓN DOCUMENTAL]:\n"
            "- Cuando se consulte por un documento formal de la biblioteca, utiliza `leer_documento_completo` para obtener el contenido íntegro y verificado.\n"
            "- Para obras y códigos extensos (> 30.000 tokens), puedes explorar su mapa estructural con `obtener_estructura_documento(doc_id=...)` o solicitar una sección específica con `leer_documento_completo(doc_id=..., seccion=\"<nombre_sección>\")`."
        )

    custom_prompt = settings.get("custom_system_prompt", "").strip()
    if custom_prompt:
        blocks.append(f"\n[DIRECTIVAS ADICIONALES]:\n{custom_prompt}")

    return "\n\n".join(blocks).strip()


async def enrich_chat_payload(
    data: Dict[str, Any],
    actual_model: str,
    is_cloud_request: bool = False,
    apply_rag_injection: bool = False
) -> Dict[str, Any]:
    """Enriquece el payload de chat completions usando la configuración dinámica de MongoDB."""
    if "messages" not in data or not isinstance(data["messages"], list):
        return data

    settings = get_alignment_settings()
    if not settings.get("enabled", True):
        return data

    messages: List[Dict[str, Any]] = data["messages"]
    tools: List[Dict[str, Any]] = data.get("tools", [])
    tool_names = []
    for t in tools:
        if isinstance(t, dict):
            fn = t.get("function", {})
            if isinstance(fn, dict) and "name" in fn:
                tool_names.append(fn["name"])

    has_pdf_tool = "generate_pdf_document" in tool_names or "generate_pdf" in tool_names
    has_doc_tool = "leer_documento_completo" in tool_names or "read_document" in tool_names

    # 1. Construir bloques del sistema
    system_parts = []
    if settings.get("inject_temporal", True):
        system_parts.append(get_current_time_str())

    invariants_block = get_invariants_system_prompt(settings, has_pdf_tool=has_pdf_tool, has_doc_tool=has_doc_tool)
    if invariants_block:
        system_parts.append(invariants_block)

    full_system_header = "\n\n".join(system_parts).strip()

    if full_system_header:
        system_msg = next((m for m in messages if m.get("role") == "system"), None)
        if system_msg:
            orig_content = system_msg.get("content", "")
            if "[DIRECTIVAS FUNDAMENTALES" not in orig_content and "Fecha y hora actual:" not in orig_content:
                system_msg["content"] = f"{full_system_header}\n\n{orig_content}".strip()
        else:
            messages.insert(0, {"role": "system", "content": full_system_header})

    # Extraer última consulta del usuario para contextualización
    last_user_msg = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    user_query = ""
    if last_user_msg:
        content_val = last_user_msg.get("content", "")
        if isinstance(content_val, str):
            user_query = content_val
        elif isinstance(content_val, list):
            text_parts = [p.get("text", "") for p in content_val if isinstance(p, dict) and p.get("type") == "text"]
            user_query = " ".join(text_parts)

    # 2. Inyección de Búsqueda Web (si es modelo web)
    if not is_cloud_request and actual_model == "gemma-4-web" and user_query:
        try:
            max_res = int(os.getenv("OLLAMA_SEARCH_MAX_RESULTS", "3"))
            web_results = await perform_ollama_web_search(user_query, max_results=max_res)
            if web_results:
                snippets = []
                for idx, r in enumerate(web_results, 1):
                    snippets.append(f"[{idx}] {r['title']}\nURL: {r['url']}\nContenido: {r['content']}")
                web_context = "\n\n".join(snippets)
                search_prompt = (
                    f"\n\n[INFORMACIÓN DE BÚSQUEDA WEB EN TIEMPO REAL (VÍA OLLAMA)]:\n"
                    f"{web_context}\n"
                    f"--------------------------------------------------\n"
                    f"Instrucciones: Utiliza la información web anterior para responder de forma precisa, "
                    f"actualizada y cita las fuentes o enlaces si es relevante."
                )
                system_msg = next((m for m in messages if m.get("role") == "system"), None)
                if system_msg:
                    system_msg["content"] = f"{system_msg.get('content', '')}{search_prompt}".strip()
        except Exception as we:
            print(f"⚠️ Error en búsqueda web Gateway: {we}", file=sys.stderr, flush=True)

    # 3. Inyección RAG Documental (LanceDB - Teccam)
    if (apply_rag_injection or actual_model == "gemma-4-rag") and user_query:
        try:
            from rag_engine import (
                search_knowledge_base,
                format_rag_context_for_llm,
                get_rag_settings,
                find_documents_by_fuzzy_title,
                get_document_full_content
            )
            rag_sett = get_rag_settings()
            if rag_sett.get("enabled", True):
                rag_context_str = ""
                matched_docs = find_documents_by_fuzzy_title(user_query)

                # Si la consulta menciona un documento específico
                if matched_docs and matched_docs[0].get("score", 0) >= 0.5:
                    top_doc = matched_docs[0]
                    full_res = get_document_full_content(top_doc["doc_id"], token_threshold=30000)
                    total_tokens = full_res.get("total_doc_tokens", 0)

                    if total_tokens <= 30000 and full_res.get("content"):
                        rag_context_str = (
                            f"--- DOCUMENTO COMPLETO OFICIAL DE LA BIBLIOTECA (Fidelidad 100%): \"{top_doc['title']}\" ---\n"
                            f"(Tema: {top_doc.get('topic', 'General')} | Autor: {top_doc.get('author', 'Desconocido')})\n\n"
                            f"{full_res.get('content')}\n\n"
                            f"--- FIN DEL DOCUMENTO OFICIAL ---"
                        )
                    else:
                        rag_results = search_knowledge_base(
                            query=user_query,
                            temas=[top_doc.get("topic")] if top_doc.get("topic") else None,
                            top_k=8
                        )
                        if rag_results:
                            rag_context_str = format_rag_context_for_llm(rag_results)

                if not rag_context_str:
                    rag_results = search_knowledge_base(query=user_query, top_k=8)
                    if rag_results:
                        rag_context_str = format_rag_context_for_llm(rag_results)

                if rag_context_str:
                    rag_prompt = (
                        f"\n\n[CONTEXTO DE LA BASE DE CONOCIMIENTO DOCUMENTAL (LANCEDB - TECCAM)]:\n"
                        f"{rag_context_str}\n"
                        f"--------------------------------------------------\n"
                        f"Instrucciones: Responde a la pregunta del usuario utilizando de manera prioritaria y rigurosa la información y fuentes proporcionadas arriba. Cita los artículos, documentos y secciones de donde proviene la información."
                    )
                    system_msg = next((m for m in messages if m.get("role") == "system"), None)
                    if system_msg:
                        system_msg["content"] = f"{system_msg.get('content', '')}{rag_prompt}".strip()
        except Exception as re_err:
            print(f"⚠️ Error en contextualización RAG: {re_err}", file=sys.stderr, flush=True)

    # 4. Tool Choice Enforcement Inteligente
    if has_pdf_tool and user_query:
        pdf_triggers = [r"\bpdf\b", r"\bdescargar\b", r"\bexportar\b", r"\bgenerar\s+pdf\b", r"\bpasamelo\s+en\s+pdf\b", r"\bformato\s+pdf\b"]
        if any(re.search(pat, user_query, re.IGNORECASE) for pat in pdf_triggers):
            if data.get("tool_choice") == "none":
                data["tool_choice"] = "auto"

    # 5. Clamping inteligente de max_tokens para evitar el bug de desborde de OpenWebUI
    if "max_tokens" in data and isinstance(data["max_tokens"], int):
        max_output_cap = int(settings.get("max_response_tokens_cap", 8192))
        if data["max_tokens"] > max_output_cap:
            data["max_tokens"] = max_output_cap

    return data
