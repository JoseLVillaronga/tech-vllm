import os
import sys
import json
import httpx
from fastapi import Request, Response


def get_env_setting(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val is not None and val.strip() != "":
        return val.strip()
    try:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == key:
                            clean_v = v.strip()
                            if (clean_v.startswith('"') and clean_v.endswith('"')) or (clean_v.startswith("'") and clean_v.endswith("'")):
                                clean_v = clean_v[1:-1]
                            return clean_v
    except Exception:
        pass
    return default


async def perform_ollama_web_search(query: str, max_results: int = 3) -> list:
    """
    Ejecuta búsquedas en la web usando la API de Ollama Cloud.
    """
    ollama_api_key = get_env_setting("OLLAMA_API_KEY", "").strip()
    search_enabled = get_env_setting("OLLAMA_SEARCH_ENABLED", "true").strip().lower() in ["true", "1", "yes"]

    if not search_enabled:
        print("⚠️ Ollama Web Search: Búsqueda web deshabilitada (OLLAMA_SEARCH_ENABLED=false)", file=sys.stderr, flush=True)
        return []

    if not ollama_api_key:
        print("⚠️ Ollama Web Search: OLLAMA_API_KEY no está configurada en .env", file=sys.stderr, flush=True)
        return []

    if not query or not query.strip():
        return []

    url = "https://ollama.com/api/web_search"
    headers = {
        "Authorization": f"Bearer {ollama_api_key}",
        "Content-Type": "application/json"
    }
    payload = {"query": query.strip()}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                formatted = []
                for item in results[:max_results]:
                    title = item.get("title", "Sin título").strip()
                    item_url = item.get("url", "").strip()
                    content = item.get("content", "").strip()
                    if len(content) > 1500:
                        content = content[:1500] + "..."
                    formatted.append({
                        "title": title,
                        "url": item_url,
                        "content": content
                    })
                return formatted
            else:
                print(f"⚠️ Ollama Web Search API error: HTTP {resp.status_code} - {resp.text}", file=sys.stderr, flush=True)
                return []
    except Exception as e:
        print(f"⚠️ Error al consultar Ollama Web Search API: {e}", file=sys.stderr, flush=True)
        return []


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

        max_results = int(tool_data.get("max_results") or os.getenv("OLLAMA_SEARCH_MAX_RESULTS", "3"))

        search_results = await perform_ollama_web_search(query, max_results=max_results)

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
