"""
title: Búsqueda y Lectura RAG Teccam (LanceDB)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Consulta y lee documentos de la base de conocimiento documental de Teccam (Constitución Nacional, Código Civil, Procedimientos Teccam, Patrones de Reingeniería, Rick Rubin) indexada en LanceDB con vectores 1024D (Qwen3) y BM25.
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 2.1.0
license: MIT
"""

import os
import requests
from typing import Optional, List, Union
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        GATEWAY_URL: str = Field(
            default="http://127.0.0.1:8000",
            description="URL base del Gateway de la suite vLLM (ej: http://127.0.0.1:8000 o https://tech-support.com.ar:19000)."
        )
        API_KEY: str = Field(
            default="TU_CLAVE_API_VLLM_AQUI",
            description="Clave API autorizada para consultar el servicio RAG."
        )
        DEFAULT_TOP_K: int = Field(
            default=4,
            description="Cantidad máxima de fragmentos relevantes a recuperar por búsqueda puntual."
        )

    def __init__(self):
        self.valves = self.Valves()

    def buscar_en_base_de_conocimiento(
        self,
        consulta: str,
        dominios: Optional[str] = None
    ) -> str:
        """
        Consulta fragmentos relevantes en la base de datos documental y jurídica de Teccam en LanceDB.
        Utiliza esta herramienta siempre que el usuario haga preguntas puntuales sobre leyes argentinas, artículos de la Constitución, Código Civil, procedimientos internos de Teccam o patrones de arquitectura.
        :param consulta: Pregunta o términos de búsqueda específicos para consultar en los libros y procedimientos.
        :param dominios: Opcional: Tema o temas a filtrar separados por comas. Dejar vacío para buscar en toda la base.
        """
        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if not base_url.endswith("/api/tools/rag-search") and not base_url.endswith("/v1/rag/search"):
            url = f"{base_url}/api/tools/rag-search"
        else:
            url = base_url

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }

        # Sanitización defensiva contra FieldInfo de Pydantic
        clean_query = str(consulta).strip() if consulta and not str(type(consulta)).endswith("FieldInfo'>") else ""
        temas_list = None
        if dominios and not str(type(dominios)).endswith("FieldInfo'>"):
            if isinstance(dominios, list):
                temas_list = [str(d).strip() for d in dominios if d]
            elif isinstance(dominios, str):
                temas_list = [d.strip() for d in dominios.split(",") if d.strip()]

        top_k_val = 4
        if hasattr(self.valves, "DEFAULT_TOP_K") and not str(type(self.valves.DEFAULT_TOP_K)).endswith("FieldInfo'>"):
            try:
                top_k_val = int(self.valves.DEFAULT_TOP_K)
            except Exception:
                top_k_val = 4

        payload = {
            "query": clean_query,
            "temas": temas_list,
            "top_k": top_k_val
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15.0)

            if response.status_code == 503:
                return "Aviso: El servicio de Base de Conocimiento RAG está temporalmente desactivado globalmente."

            if response.status_code != 200:
                return f"Error en la consulta RAG (HTTP {response.status_code}): {response.text}"

            data = response.json()
            context = data.get("context", "")
            results_count = data.get("results_count", 0)

            if not context or results_count == 0:
                return f"No se encontraron fragmentos relevantes en la base de conocimiento para la consulta: '{clean_query}'."

            return (
                f"[DOCUMENTOS ENCONTRADOS EN LANCEDB ({results_count} fragmentos recuperados en {data.get('latency_ms', 0)} ms)]:\n\n"
                f"{context}\n\n"
                f"Por favor responde fundamentando con estos fragmentos y cita las fuentes/artículos relevantes."
            )
        except Exception as e:
            return f"Error de conexión con el Gateway RAG ({url}): {str(e)}"

    def leer_documento_completo(
        self,
        doc_id: str,
        parte: int = 1,
        seccion: Optional[str] = None
    ) -> str:
        """
        Obtiene el texto completo, por sección temática o paginado de un documento, procedimiento o libro oficial de Teccam para redactar resúmenes integrales, síntesis ejecutivas o análisis normativos exhaustivos sin omitir pasos ni incisos.
        Acepta tanto el doc_id hexadecimal como el título exacto o parcial del procedimiento/libro.
        Si el documento tiene hasta 60.000 tokens (~50% de la ventana de 128K), entrega el texto original íntegro 1:1. Si es más extenso, entrega la parte solicitada con límites limpios de sección o la sección indicada.
        :param doc_id: ID único del documento (ej: '67b2111008223c9b3c3e5608') o el título del documento (ej: 'Procedimiento General de Soporte en Puestos de Trabajo').
        :param parte: Número de parte a recuperar si es un libro extenso paginado (1 para la primera parte, 2 para la siguiente, etc.).
        :param seccion: Opcional: Nombre del capítulo, libro o sección temática específica a extraer (ej: 'Libro Primero', 'Título II', 'DESARROLLO', 'Nuevos derechos').
        """
        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if not base_url.endswith("/api/tools/rag-document") and not base_url.endswith("/v1/rag/document"):
            url = f"{base_url}/api/tools/rag-document"
        else:
            url = base_url

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }

        clean_doc_id = str(doc_id).strip() if doc_id and not str(type(doc_id)).endswith("FieldInfo'>") else ""
        clean_parte = 1
        if parte is not None and not str(type(parte)).endswith("FieldInfo'>"):
            try:
                clean_parte = int(parte)
            except Exception:
                clean_parte = 1

        clean_seccion = str(seccion).strip() if seccion and not str(type(seccion)).endswith("FieldInfo'>") else None

        payload = {
            "doc_id": clean_doc_id,
            "parte": clean_parte,
            "token_threshold": 60000,
            "seccion": clean_seccion
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=25.0)

            if response.status_code == 503:
                return "Aviso: El servicio de Base de Conocimiento RAG está temporalmente desactivado globalmente."

            if response.status_code != 200:
                return f"Error al leer el documento (HTTP {response.status_code}): {response.text}"

            data = response.json()
            return data.get("content", "")
        except Exception as e:
            return f"Error de conexión con el Gateway RAG ({url}): {str(e)}"

    def obtener_estructura_documento(
        self,
        doc_id: str
    ) -> str:
        """
        Obtiene el 'GPS Documental' (Mapa y Árbol de Estructura de Secciones) de una obra, libro o código extenso (ej: Código Civil, Constitución Nacional, manuales técnicos).
        Permite conocer todos los capítulos, títulos, artículos, rangos de fragmentos y volumen de tokens antes de leer o resumir partes específicas.
        :param doc_id: ID único del documento (ej: '6a8b02cface6becbcb49b20d') o título de la obra (ej: 'Codigo Civil Argentino').
        """
        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if not base_url.endswith("/api/tools/rag-structure") and not base_url.endswith("/v1/rag/structure"):
            url = f"{base_url}/api/tools/rag-structure"
        else:
            url = base_url

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }

        clean_doc_id = str(doc_id).strip() if doc_id and not str(type(doc_id)).endswith("FieldInfo'>") else ""
        payload = {"doc_id": clean_doc_id}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20.0)

            if response.status_code == 503:
                return "Aviso: El servicio de Base de Conocimiento RAG está temporalmente desactivado globalmente."

            if response.status_code != 200:
                return f"Error consultando estructura RAG (HTTP {response.status_code}): {response.text}"

            data = response.json()
            return data.get("content", "No se obtuvo contenido de estructura.")
        except Exception as e:
            return f"Error de conexión con el Gateway RAG ({url}): {str(e)}"

    def obtener_indice_biblioteca(
        self,
        solo_vigentes: bool = False,
        dominio: Optional[str] = None
    ) -> str:
        """
        Obtiene el 'Mapa Ontológico Global' y el Índice Jerárquico Completo de toda la biblioteca de conocimiento disponible en Teccam.
        Muestra todas las obras organizadas por ramas temáticas (Derecho Argentino, Procedimientos Teccam, Filosofía/Ética, etc.), con su estado de vigencia [VIGENTE, DEROGADO, PARCIALMENTE VIGENTE, EN PROYECTO], IDs y tokens.
        Utiliza esta herramienta como primer paso para auto-orientarte cuando no sepas qué documentos existen o quieras explorar el catálogo macro.
        :param solo_vigentes: Si es True, filtra exclusivamente obras y normas vigentes.
        :param dominio: Opcional: Filtrar por un dominio específico (ej: 'Derecho', 'Filosofia', 'Teccam').
        """
        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if not base_url.endswith("/api/tools/rag-library-index") and not base_url.endswith("/v1/rag/library-index"):
            url = f"{base_url}/api/tools/rag-library-index"
        else:
            url = base_url

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }

        clean_dominio = str(dominio).strip() if dominio and not str(type(dominio)).endswith("FieldInfo'>") else None
        is_solo_vigentes = bool(solo_vigentes) if not str(type(solo_vigentes)).endswith("FieldInfo'>") else False

        payload = {
            "solo_vigentes": is_solo_vigentes,
            "tema": clean_dominio
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20.0)

            if response.status_code == 503:
                return "Aviso: El servicio de Base de Conocimiento RAG está temporalmente desactivado globalmente."

            if response.status_code != 200:
                return f"Error consultando índice de biblioteca RAG (HTTP {response.status_code}): {response.text}"

            data = response.json()
            return data.get("content", "No se obtuvo contenido del índice de la biblioteca.")
        except Exception as e:
            return f"Error de conexión con el Gateway RAG ({url}): {str(e)}"

