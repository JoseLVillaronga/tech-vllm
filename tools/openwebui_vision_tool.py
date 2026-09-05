"""
title: Visión y OCR Agéntico (Qwen2.5-VL en RAM)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Analiza imágenes, fotografías, diagramas y realiza OCR denso de documentos, recibos y textos en español mediante el microservicio desacoplado de visión de vLLM Suite ejecutado en RAM (Qwen2.5-VL-3B).
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 1.0.0
license: MIT
"""

import requests
from typing import Optional, List, Dict, Any
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

    def __init__(self):
        self.valves = self.Valves()

    def analizar_o_leer_imagen(
        self,
        imagen: Optional[str] = None,
        instruccion: Optional[str] = None,
        __messages__: Optional[List[Dict[str, Any]]] = None,
        __files__: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Inspecciona, analiza y describe imágenes, fotos, diagramas, esquemas o realiza transcripción OCR de documentos, recibos y capturas de pantalla.
        Úsalo CADA VEZ que el usuario adjunte una imagen, pregunte por una foto o archivo visual, comparta una URL/ruta de imagen o pida extraer datos de un documento gráfico.

        :param imagen: Opcional si hay una imagen adjunta en el chat. Ruta local del archivo de imagen, URL pública (http/https), o cadena base64. Si se omite, la herramienta detecta automáticamente la imagen adjunta.
        :param instruccion: Pregunta u orden específica para el análisis (ej: 'transcribe todo el texto de esta factura', 'qué componentes tiene este diagrama', 'extrae los números y fechas'). Si se omite, se realizará una descripción y OCR exhaustivo general.
        :return: Transcripción textual y descripción detallada emitida por el motor de visión Qwen2.5-VL.
        """
        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if not base_url.endswith("/api/tools/vision") and not base_url.endswith("/v1/tools/vision"):
            endpoint_url = f"{base_url}/api/tools/vision"
        else:
            endpoint_url = base_url

        target_image = str(imagen).strip() if imagen and not str(type(imagen)).endswith("FieldInfo'>") else ""
        prompt_text = str(instruccion).strip() if instruccion and not str(type(instruccion)).endswith("FieldInfo'>") else ""

        # Auto-detección en archivos adjuntos de Open-WebUI si no se pasó ruta explícita
        if not target_image and __files__ and isinstance(__files__, list):
            for f in __files__:
                if isinstance(f, dict):
                    # Puede ser URL, path o base64
                    img_url = f.get("url") or f.get("path") or f.get("file_path")
                    if img_url:
                        target_image = img_url
                        break

        # Auto-detección en el historial de mensajes de Open-WebUI si viene en multimodal content
        if not target_image and __messages__ and isinstance(__messages__, list):
            for msg in reversed(__messages__):
                content = msg.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "image_url":
                            img_obj = part.get("image_url", {})
                            url_val = img_obj.get("url") if isinstance(img_obj, dict) else str(img_obj)
                            if url_val:
                                target_image = url_val
                                break
                if target_image:
                    break

        if not target_image:
            return (
                "⚠️ Error de Visión: No se detectó ninguna imagen para analizar. "
                "Por favor, adjunta una imagen en el chat o proporciona la ruta/URL del archivo de imagen."
            )

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "image": target_image,
            "prompt": prompt_text or "Analiza y describe exhaustivamente el contenido de esta imagen o documento, extrayendo cualquier texto, tabla o dato visible."
        }

        try:
            resp = requests.post(endpoint_url, headers=headers, json=payload, timeout=75.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    analysis = data.get("analysis") or data.get("text") or "Análisis completado sin texto de salida."
                    return f"### 👁️ Análisis de Imagen (Qwen2.5-VL):\n\n{analysis}"
                else:
                    return f"⚠️ Error reportado por el motor de visión: {data.get('error', 'Error desconocido')}"
            else:
                return f"⚠️ Error HTTP {resp.status_code} al consultar el servicio de visión en el Gateway: {resp.text}"
        except requests.exceptions.Timeout:
            return "⏳ Tiempo de espera agotado al consultar el microservicio de visión (CPU en RAM). Intenta con una imagen más liviana."
        except Exception as err:
            return f"⚠️ Excepción al invocar la herramienta de visión: {err}"
