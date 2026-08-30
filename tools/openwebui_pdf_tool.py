"""
title: Generador de Documentos y Contratos en PDF A4
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Genera documentos PDF profesionales en formato A4 con diseño ejecutivo, fórmulas matemáticas/químicas limpias, centrado multilínea y enlace de descarga directa con auto-limpieza TTL.
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 2.0.0
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
            description="Clave API autorizada en vLLM Suite Gateway."
        )
        COMPANY_NAME: str = Field(
            default="Teccam S.R.L.",
            description="Nombre de la empresa o membrete oficial para el pie de página de los PDFs."
        )

    def __init__(self):
        self.valves = self.Valves()

    def generate_pdf_document(
        self,
        title: str = "Documento Oficial",
        filename: Optional[str] = None,
        markdown_content: str = ""
    ) -> str:
        """
        Genera un archivo PDF profesional en formato A4 a partir de contenido en Markdown y devuelve el enlace de descarga directa.
        Úsalo cada vez que el usuario te pida crear, redactar o exportar contratos, acuerdos, informes, cartas formales o documentos en PDF.
        
        :param title: Título principal del documento (ej: 'CONTRATO DE LOCACIÓN DE INMUEBLE', 'INFORME EJECUTIVO').
        :param filename: Nombre sugerido para el archivo PDF (ej: 'contrato_locacion.pdf', 'informe_ejecutivo.pdf').
        :param markdown_content: El contenido completo del documento redactado en Markdown con secciones, viñetas y tablas.
        :return: Enlace de descarga e información del documento.
        """
        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if not base_url.endswith("/api/tools/generate-pdf"):
            url = f"{base_url}/api/tools/generate-pdf"
        else:
            url = base_url

        clean_title = str(title).strip() if title and not str(type(title)).endswith("FieldInfo'>") else "Documento Oficial"
        clean_content = str(markdown_content).strip() if markdown_content and not str(type(markdown_content)).endswith("FieldInfo'>") else ""

        # Fallback si el modelo invirtió los parámetros
        if not clean_content and clean_title and clean_title != "Documento Oficial":
            clean_content = clean_title
            clean_title = "Documento Oficial"

        clean_filename = str(filename).strip() if filename and not str(type(filename)).endswith("FieldInfo'>") else ""
        if not clean_filename:
            clean_filename = f"{clean_title.lower().replace(' ', '_')}.pdf"
        if not clean_filename.lower().endswith(".pdf"):
            clean_filename += ".pdf"

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "title": clean_title,
            "markdown_content": clean_content,
            "filename": clean_filename,
            "company_name": str(self.valves.COMPANY_NAME)
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                dl_url = data.get("download_url", "")
                pages = data.get("pages", 1)
                size_kb = data.get("size_kb", 0)

                return (
                    f"✅ Documento PDF generado exitosamente.\n\n"
                    f"📄 **{clean_title}**\n"
                    f"🔗 **Enlace de descarga:** [📥 Descargar {clean_filename}]({dl_url})\n"
                    f"*(Páginas: {pages} | Tamaño: {size_kb} KB)*"
                )

            return f"❌ Error al generar PDF en Gateway: HTTP {resp.status_code} - {resp.text}"
        except Exception as e:
            return f"❌ Error conectando con el servicio de generación de PDF: {str(e)}"
