"""
title: Búsqueda RAG Teccam (LanceDB)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Consulta la base de conocimiento documental de Teccam (Constitución Nacional, Código Civil Ley 340, Procedimientos Teccam, Patrones de Reingeniería, Rick Rubin) indexada en LanceDB con vectores 1024D (Qwen3) y BM25.
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 1.0.0
license: MIT
"""

import os
import requests
from typing import Optional, List, Union
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        GATEWAY_URL: str = Field(
            default="http://127.0.0.1:8000/v1/rag/search",
            description="URL del endpoint de búsqueda RAG en el Gateway de la suite vLLM."
        )
        API_KEY: str = Field(
            default="token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939",
            description="Clave API autorizada para consultar el servicio RAG."
        )
        DEFAULT_TOP_K: int = Field(
            default=4,
            description="Cantidad máxima de fragmentos relevantes a recuperar por búsqueda."
        )

    def __init__(self):
        self.valves = self.Valves()

    def buscar_en_base_de_conocimiento(
        self,
        consulta: str = Field(
            ...,
            description="Pregunta o términos de búsqueda específicos para consultar en los libros y procedimientos (ej: 'artículo 14 bis constitución', 'funciones del responsable de soporte en Teccam', 'patrón de reingeniería código espagueti')."
        ),
        dominios: Optional[List[str]] = Field(
            None,
            description="Opcional: Lista de dominios/temas a restringir. Opciones: ['Derecho Argentino', 'Procedimientos Teccam', 'Estrategia', 'Filosofía']. Dejar vacío para buscar en toda la base."
        )
    ) -> str:
        """
        Consulta la base de datos documental y jurídica de Teccam en LanceDB.
        Utiliza esta herramienta siempre que el usuario haga preguntas sobre leyes argentinas, artículos de la Constitución, Código Civil, procedimientos internos de Teccam, arquitectura/reingeniería de software o filosofía.
        """
        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": consulta,
            "temas": dominios if dominios else None,
            "top_k": self.valves.DEFAULT_TOP_K
        }

        try:
            response = requests.post(
                self.valves.GATEWAY_URL,
                json=payload,
                headers=headers,
                timeout=12.0
            )

            if response.status_code == 503:
                return "Aviso: El servicio de Base de Conocimiento RAG está temporalmente desactivado globalmente."

            if response.status_code != 200:
                return f"Error en la consulta RAG (HTTP {response.status_code}): {response.text}"

            data = response.json()
            context = data.get("context", "")
            results_count = data.get("results_count", 0)

            if not context or results_count == 0:
                return "No se encontraron fragmentos relevantes en la base de conocimiento para esta consulta."

            return (
                f"[DOCUMENTOS ENCONTRADOS EN LANCEDB ({results_count} fragmentos recuperados en {data.get('latency_ms', 0)} ms)]:\n\n"
                f"{context}\n\n"
                f"Por favor responde fundamentando con estos fragmentos y cita las fuentes/artículos relevantes."
            )
        except Exception as e:
            return f"Error de conexión con el motor RAG LanceDB: {str(e)}"
