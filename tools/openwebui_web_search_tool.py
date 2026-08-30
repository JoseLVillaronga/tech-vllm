"""
title: Búsqueda Web en Vivo (Ollama Cloud)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Realiza búsquedas web en internet en tiempo real para obtener noticias, hechos recientes y páginas web mediante el Gateway de vLLM Suite (Ollama Cloud).
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 1.2.0
license: MIT
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        GATEWAY_URL: str = Field(
            default="https://tech-support.com.ar:19000",
            description="URL base del Gateway de vLLM Suite (ej: http://127.0.0.1:8000 o https://tech-support.com.ar:19000)."
        )
        API_KEY: str = Field(
            default="TU_API_KEY_AQUI",
            description="Clave API registrada en vLLM Suite Gateway."
        )
        MAX_RESULTS: int = Field(
            default=3,
            description="Cantidad máxima de resultados web a recuperar por búsqueda (1 a 5)."
        )

    def __init__(self):
        self.valves = self.Valves()

    def buscar_en_internet(
        self,
        consulta: str,
        max_resultados: Optional[int] = None
    ) -> str:
        """
        Realiza una búsqueda en la web en tiempo real para obtener noticias de hoy, datos recientes, artículos y fuentes externas.
        Úsalo cada vez que el usuario pregunte por noticias actuales, eventos recientes, cotizaciones, clima o temas que requieran verificación web.
        
        :param consulta: Términos o frase de búsqueda en internet (ej: 'noticias buenos aires hoy', 'precio del dólar').
        :param max_resultados: Cantidad de resultados deseados (por defecto 3).
        :return: Fragmentos web formateados con títulos, URLs y resúmenes.
        """
        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if not base_url.endswith("/api/tools/web-search"):
            url = f"{base_url}/api/tools/web-search"
        else:
            url = base_url

        clean_query = str(consulta).strip() if consulta and not str(type(consulta)).endswith("FieldInfo'>") else ""
        num_res = 3
        if max_resultados is not None and not str(type(max_resultados)).endswith("FieldInfo'>"):
            try:
                num_res = int(max_resultados)
            except Exception:
                num_res = 3
        elif hasattr(self.valves, "MAX_RESULTS") and not str(type(self.valves.MAX_RESULTS)).endswith("FieldInfo'>"):
            try:
                num_res = int(self.valves.MAX_RESULTS)
            except Exception:
                num_res = 3

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": clean_query,
            "max_results": num_res
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20.0)
            if response.status_code != 200:
                return f"Error en búsqueda web (HTTP {response.status_code}): {response.text}"

            data = response.json()
            if not data.get("success", False) or not data.get("results"):
                return f"No se encontraron resultados web para '{clean_query}'."

            return data.get("formatted_context", "")
        except Exception as e:
            return f"Error conectando con el servicio de búsqueda web: {str(e)}"
