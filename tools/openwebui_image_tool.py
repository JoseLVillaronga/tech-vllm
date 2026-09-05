"""
title: Generación de Imágenes Agéntica (SDXL-Turbo en RAM/CPU)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Genera y renderiza imágenes artísticas, técnicas o fotorrealistas mediante el microservicio desacoplado de difusión en CPU (SDXL-Turbo / stable-diffusion.cpp en RAM) de vLLM Suite con 0 MB de VRAM.
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 1.0.0
license: MIT
"""

import requests
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        GATEWAY_URL: str = Field(
            default="https://tech-support.com.ar:19000",
            description="URL base del endpoint en el Gateway de vLLM Suite (ej: https://tech-support.com.ar:19000 o http://127.0.0.1:8000)."
        )
        API_KEY: str = Field(
            default="token-e68f0c0d4d4f4d04d70399323d411290b2bf938a81f26685602140c4f8617939",
            description="Clave API autorizada en vLLM Suite Gateway."
        )
        MODEL: str = Field(
            default="stabilityai/sdxl-turbo",
            description="Identificador del modelo de difusión."
        )
        SIZE: str = Field(
            default="512x512",
            description="Resolución de la imagen generada (512x512 recomendada para inferencia ultrarrápida en CPU)."
        )

    def __init__(self):
        self.valves = self.Valves()

    def generar_imagen(
        self,
        prompt: str
    ) -> str:
        """
        Genera, dibuja y renderiza una imagen fotorrealista, artística, conceptual o técnica a partir de una descripción detallada en texto.
        Úsalo CADA VEZ que el usuario solicite explícitamente dibujar, crear, ilustrar, generar o visualizar una imagen, foto, paisaje, objeto, logotipo o diseño.
        
        INSTRUCCIÓN DE CALIDAD PARA EL MODELO:
        Formula o traduce la descripción (prompt) al idioma INGLÉS con detalles descriptivos de iluminación, composición y estilo (por ejemplo: 'A futuristic electric car in a rainy cyberpunk city at night, neon lights reflections, cinematic lighting, 8k, photorealistic') para obtener la más alta fidelidad en el modelo de difusión.

        :param prompt: Descripción visual detallada en inglés de la imagen a generar.
        :return: Bloque Markdown con la imagen embebida en Base64 lista para ser renderizada en el chat de Open-WebUI.
        """
        clean_prompt = str(prompt).strip() if prompt and not str(type(prompt)).endswith("FieldInfo'>") else ""
        if not clean_prompt:
            return "⚠️ No se especificó una descripción (prompt) válida para generar la imagen."

        base_url = str(self.valves.GATEWAY_URL).rstrip("/")
        if base_url.endswith("/images/generations"):
            endpoint_url = base_url
        elif base_url.endswith("/v1"):
            endpoint_url = f"{base_url}/images/generations"
        else:
            endpoint_url = f"{base_url}/v1/images/generations"

        headers = {
            "Authorization": f"Bearer {self.valves.API_KEY.strip()}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": clean_prompt,
            "model": self.valves.MODEL,
            "size": self.valves.SIZE,
            "response_format": "url"
        }

        try:
            resp = requests.post(endpoint_url, headers=headers, json=payload, timeout=120.0)

            if resp.status_code == 200:
                data = resp.json()
                data_list = data.get("data", [])
                if data_list and isinstance(data_list, list):
                    first_obj = data_list[0]

                    # Caso 1 (Prioritario): Retornar URL pública para no colapsar la ventana de contexto del LLM
                    img_url = first_obj.get("url")
                    if img_url:
                        if img_url.startswith("/"):
                            clean_base = base_url.replace("/v1/images/generations", "").replace("/images/generations", "").replace("/v1", "").rstrip("/")
                            img_url = f"{clean_base}{img_url}"

                        return (
                            f"![{clean_prompt}]({img_url})\n\n"
                            f"🎨 **Imagen generada exitosamente con SDXL-Turbo (CPU/RAM)**\n"
                            f"*Prompt:* `{clean_prompt}`"
                        )

                    # Caso 2 (Fallback): Imagen en base64 si el backend no proporcionó URL
                    b64_data = first_obj.get("b64_json")
                    if b64_data:
                        return (
                            f"![{clean_prompt}](data:image/png;base64,{b64_data})\n\n"
                            f"🎨 **Imagen generada exitosamente con SDXL-Turbo (CPU/RAM)**\n"
                            f"*Prompt:* `{clean_prompt}`"
                        )

                return "⚠️ La solicitud fue exitosa pero no se recibió ninguna imagen en el formato esperado."

            elif resp.status_code == 401:
                return "❌ Error de autenticación (401): API Key inválida o no configurada en las válvulas de la herramienta."
            elif resp.status_code == 403:
                return "❌ Error de permisos (403): La API Key no tiene permisos autorizados para el servicio de imágenes."
            else:
                return f"❌ Error en el servidor de generación de imágenes (HTTP {resp.status_code}): {resp.text}"

        except requests.exceptions.Timeout:
            return "⏳ Tiempo de espera agotado al generar la imagen (el servidor tardó más de 120 segundos)."
        except requests.exceptions.ConnectionError:
            return f"❌ Error de conexión: No se pudo contactar al Gateway en {endpoint_url}. Verifica que el servicio esté activo."
        except Exception as e:
            return f"❌ Error inesperado al invocar la herramienta de generación de imágenes: {str(e)}"
