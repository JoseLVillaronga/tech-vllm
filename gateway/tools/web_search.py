import os
import sys
import json
from typing import Optional
import httpx
from fastapi import Request, Response

from config import env

# Alias unificado hacia config.env
get_env_setting = env


async def perform_deepseek_web_search(query: str, max_results: Optional[int] = None) -> list:
    """
    Ejecuta búsquedas en la web usando la API oficial de DeepSeek Search.
    Precondiciones: DEEPSEEK_SEARCH_ENABLED=true, DEEPSEEK_API_KEY y DEEPSEEK_SEARCH_URL definidos en .env.
    """
    deepseek_api_key = get_env_setting("DEEPSEEK_API_KEY", "").strip()
    deepseek_url = get_env_setting("DEEPSEEK_SEARCH_URL", "").strip()
    search_enabled = get_env_setting("DEEPSEEK_SEARCH_ENABLED", "false").strip().lower() in ["true", "1", "yes"]

    if not search_enabled:
        return []

    if not deepseek_api_key or not deepseek_url:
        print(
            "⚠️ [WebSearch:DeepSeek] Fallo de configuración: DEEPSEEK_API_KEY o DEEPSEEK_SEARCH_URL ausentes en .env.",
            file=sys.stderr,
            flush=True
        )
        return []

    if not query or not query.strip():
        return []

    eff_max = int(max_results or get_env_setting("DEEPSEEK_SEARCH_MAX_RESULTS", "3") or 3)
    eff_max = max(1, min(50, eff_max))
    # DeepSeek Search API exige entre 1 y 128 caracteres Unicode en 'query'
    clean_query = query.strip()[:128]

    headers = {
        "Authorization": f"Bearer {deepseek_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": clean_query,
        "count": eff_max,
        "need_content": True
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(deepseek_url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                formatted = []
                for item in results[:eff_max]:
                    title = (item.get("title") or "Sin título").strip()
                    item_url = (item.get("url") or "").strip()
                    summary = (item.get("summary") or "").strip()
                    raw_content = (item.get("content") or "").strip()
                    snippet = (item.get("snippet") or "").strip()

                    if summary and raw_content and not raw_content.startswith(summary[:60]):
                        body = f"{summary}\n{raw_content}".strip()
                    else:
                        body = summary or raw_content or snippet

                    if len(body) > 1500:
                        body = body[:1500] + "..."

                    formatted.append({
                        "title": title,
                        "url": item_url,
                        "content": body
                    })
                return formatted
            else:
                print(
                    f"⚠️ [WebSearch:DeepSeek] Error HTTP {resp.status_code}: {resp.text[:200]}",
                    file=sys.stderr,
                    flush=True
                )
                return []
    except Exception as exc:
        print(f"⚠️ [WebSearch:DeepSeek] Excepción de red: {exc}", file=sys.stderr, flush=True)
        return []


async def perform_ollama_web_search_direct(query: str, max_results: Optional[int] = None) -> list:
    """
    Ejecuta búsquedas en la web usando la API de Ollama Cloud.
    Precondiciones: OLLAMA_SEARCH_ENABLED=true, OLLAMA_API_KEY y OLLAMA_SEARCH_URL definidos en .env.
    """
    ollama_api_key = get_env_setting("OLLAMA_API_KEY", "").strip()
    ollama_url = get_env_setting("OLLAMA_SEARCH_URL", "").strip()
    search_enabled = get_env_setting("OLLAMA_SEARCH_ENABLED", "true").strip().lower() in ["true", "1", "yes"]

    if not search_enabled:
        return []

    if not ollama_api_key or not ollama_url:
        print(
            "⚠️ [WebSearch:Ollama] Fallo de configuración: OLLAMA_API_KEY o OLLAMA_SEARCH_URL ausentes en .env.",
            file=sys.stderr,
            flush=True
        )
        return []

    if not query or not query.strip():
        return []

    eff_max = int(max_results or get_env_setting("OLLAMA_SEARCH_MAX_RESULTS", "3") or 3)
    headers = {
        "Authorization": f"Bearer {ollama_api_key}",
        "Content-Type": "application/json"
    }
    payload = {"query": query.strip()}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(ollama_url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                formatted = []
                for item in results[:eff_max]:
                    title = (item.get("title") or "Sin título").strip()
                    item_url = (item.get("url") or "").strip()
                    content = (item.get("content") or "").strip()
                    if len(content) > 1500:
                        content = content[:1500] + "..."
                    formatted.append({
                        "title": title,
                        "url": item_url,
                        "content": content
                    })
                return formatted
            else:
                print(
                    f"⚠️ [WebSearch:Ollama] Error HTTP {resp.status_code}: {resp.text[:200]}",
                    file=sys.stderr,
                    flush=True
                )
                return []
    except Exception as exc:
        print(f"⚠️ [WebSearch:Ollama] Excepción de red: {exc}", file=sys.stderr, flush=True)
        return []


async def perform_web_search(query: str, max_results: Optional[int] = None) -> list:
    """
    Despachador unificado de búsqueda web con prioridad en DeepSeek y fallback automático a Ollama.
    """
    if not query or not query.strip():
        return []

    ds_enabled = get_env_setting("DEEPSEEK_SEARCH_ENABLED", "false").strip().lower() in ["true", "1", "yes"]
    ol_enabled = get_env_setting("OLLAMA_SEARCH_ENABLED", "true").strip().lower() in ["true", "1", "yes"]

    if not ds_enabled and not ol_enabled:
        print("⚠️ [WebSearch] Búsqueda web deshabilitada en .env (DEEPSEEK_SEARCH_ENABLED=false y OLLAMA_SEARCH_ENABLED=false).", file=sys.stderr, flush=True)
        return []

    if ds_enabled:
        ds_results = await perform_deepseek_web_search(query, max_results=max_results)
        if ds_results:
            return ds_results
        if ol_enabled:
            print("🔄 [WebSearch] Conmutando a Ollama Web Search como fallback tras respuesta vacía/error de DeepSeek.", flush=True)
            return await perform_ollama_web_search_direct(query, max_results=max_results)
        return []

    return await perform_ollama_web_search_direct(query, max_results=max_results)


# Mantener alias de compatibilidad hacia atrás para todos los módulos consumidores
perform_ollama_web_search = perform_web_search


async def handle_web_search(request: Request) -> Response:
    """
    Manejador para el endpoint POST /api/tools/web-search.
    """
    try:
        tool_body = await request.body()
        tool_data = json.loads(tool_body) if tool_body else {}

        query = ""
        if "query" in tool_data:
            query = tool_data["query"]
        elif "input" in tool_data:
            query = tool_data["input"]
        elif "arguments" in tool_data and isinstance(tool_data["arguments"], dict):
            query = tool_data["arguments"].get("query", "")
        elif "arguments" in tool_data and isinstance(tool_data["arguments"], str):
            try:
                arg_obj = json.loads(tool_data["arguments"])
                query = arg_obj.get("query", "")
            except Exception:
                query = tool_data["arguments"]
        elif "messages" in tool_data:
            user_msgs = [m.get("content", "") for m in tool_data["messages"] if m.get("role") == "user"]
            if user_msgs:
                query = user_msgs[-1]

        max_results_raw = tool_data.get("max_results")
        max_results = int(max_results_raw) if max_results_raw is not None else None

        search_results = await perform_web_search(query, max_results=max_results)

        formatted_snippets = []
        for idx, item in enumerate(search_results, 1):
            formatted_snippets.append(
                f"[{idx}] {item['title']}\n"
                f"URL: {item['url']}\n"
                f"Contenido: {item['content']}"
            )
        formatted_text = "\n\n".join(formatted_snippets) if formatted_snippets else "No se encontraron resultados web para la consulta."

        response_payload = {
            "success": True,
            "query": query,
            "count": len(search_results),
            "results": search_results,
            "formatted_context": formatted_text,
            "text": formatted_text
        }

        return Response(
            content=json.dumps(response_payload),
            media_type="application/json",
            status_code=200
        )
    except Exception as tool_err:
        print(f"⚠️ Error procesando tool de búsqueda web: {tool_err}", file=sys.stderr, flush=True)
        return Response(
            content=json.dumps({"success": False, "error": str(tool_err)}),
            media_type="application/json",
            status_code=500
        )
