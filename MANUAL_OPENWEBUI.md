# 📘 Manual de Integración y Guía de Uso: vLLM Suite + Open-WebUI

Este manual describe en detalle cómo configurar, optimizar y operar la suite de inteligencia artificial **vLLM Suite** en conjunto con la interfaz de usuario **Open-WebUI**, aprovechando la inferencia local de alta velocidad, búsqueda web en tiempo real, base de conocimiento RAG (LanceDB), generación de PDFs ejecutivos y herramientas personalizadas (*Custom Tools*).

---

## 📑 Tabla de Contenidos
1. [Arquitectura de Conexión y Endpoints](#1-arquitectura-de-conexión-y-endpoints)
2. [Configuración de Modelos y Parámetros Clave](#2-configuración-de-modelos-y-parámetros-clave)
3. [Catálogo de Herramientas Personalizadas (Custom Tools)](#3-catálogo-de-herramientas-personalizadas-custom-tools)
   * [Herramienta 1: Búsqueda y Lectura RAG Teccam (LanceDB)](#herramienta-1-búsqueda-y-lectura-rag-teccam-lancedb)
   * [Herramienta 2: Generador de Documentos en PDF A4](#herramienta-2-generador-de-documentos-en-pdf-a4)
   * [Herramienta 3: Búsqueda Web en Vivo (Ollama Cloud)](#herramienta-3-búsqueda-web-en-vivo-ollama-cloud)
   * [Herramienta 4: Clima y Pronóstico Extendido (OpenWeatherMap)](#herramienta-4-clima-y-pronóstico-extendido-openweathermap)
4. [Metodología de Consulta Eficiente (Técnica del Embudo Progresivo / Scaffolding Cognitivo)](#4-metodología-de-consulta-eficiente-técnica-del-embudo-progresivo--scaffolding-cognitivo)
5. [Flujos de Trabajo Combinados (Casos Prácticos)](#5-flujos-de-trabajo-combinados-casos-prácticos)
6. [Guía de Buenas Prácticas y Solución de Problemas (FAQ)](#6-guía-de-buenas-prácticas-y-solución-de-problemas-faq)

---

## 1. Arquitectura de Conexión y Endpoints

La suite expone sus servicios a través del **Gateway de Seguridad**, que gestiona la autenticación RBAC, las cuotas de tokens, el baneo automático contra intrusiones (Fail2ban) y el proxying hacia los motores de inferencia:

```
                  +-------------------------------------------------------------+
                  |                         OPEN-WEBUI                          |
                  +-------------------------------------------------------------+
                     | (19000/v1)              | (19005/v1)          | (19020/v1)
                     v                         v                     v
              +-------------+           +-------------+       +-------------+
              | Caddy Proxy |           | Caddy Proxy |       | Caddy Proxy |
              +-------------+           +-------------+       +-------------+
                     | (8000)                  | (8005)              | (8020)
                     v                         v                     v
              +-------------------------------------------------------------+
              |               vLLM Suite Gateway (Modular v2.0)             |
              |     [IP Filter] + [Fail2ban 48h] + [Auth Bearer/X-Api-Key]  |
              +-------------------------------------------------------------+
                     |                         |                     |
                     v (18000)                 v (18005)             v (5020)
              +-------------+           +-------------+       +-------------+
              | vLLM Gemma4 |           | Qwen3 Embed |       |   Docling   |
              +-------------+           +-------------+       +-------------+
```

### Configuración de Conexiones en Open-WebUI:

Ve al menú **Panel de Administración** ➔ **Ajustes** ➔ **Conexiones**:

1. **Conexión de Modelos de Chat e Inferencia:**
   * **URL Base:** `https://tech-support.com.ar:19000/v1` (o `http://127.0.0.1:8000/v1` en red local)
   * **Clave API:** `vllm_key_...` (Clave autorizada con servicio `gemma`)
2. **Conexión de Embeddings Documentales:**
   * Ve a **Ajustes ➔ Documentos ➔ Motor de Incrustación (Embedding)**
   * **Motor:** `OpenAI`
   * **URL Base:** `https://tech-support.com.ar:19005/v1` (o `http://127.0.0.1:8005/v1`)
   * **Modelo:** `Qwen/Qwen3-Embedding-0.6B`
   * **Clave API:** `vllm_key_...` (Clave autorizada con servicio `embeddings`)
3. **Conexión de Extracción de Documentos (Docling):**
   * Ve a **Ajustes ➔ Documentos ➔ Motor de Análisis de Documentos**
   * **Tipo:** `Docling`
   * **URL del Servidor:** `https://tech-support.com.ar:19020` (o `http://127.0.0.1:8020`)
   * **Clave API:** `vllm_key_...` (Open-WebUI la envía mediante la cabecera `X-Api-Key`)

> [!IMPORTANT]
> **Seguridad Fail2ban Activa:** Si un cliente envía 3 intentos consecutivos con una clave API errónea en un período de 5 minutos, la IP del cliente queda **automáticamente bloqueada por 48 horas** en MongoDB con índice TTL.

---

## 2. Configuración de Modelos y Parámetros Clave

### A. Catálogo de Modelos Locales y Virtuales
En Open-WebUI verás los modelos organizados con el prefijo **`local/`**:
* `local/google/gemma-4-E4B-it`: Modelo base de razonamiento de alto rendimiento.
* `local/gemma-4-web`: Modelo con búsqueda web en vivo inyectada automáticamente en cada consulta.
* `local/gemma-4-rag`: Modelo con inyección automática de contexto documental desde LanceDB.

---

### B. Prompt de Sistema en Dos Fases (Pensamiento vs. Respuesta Final)

Para evitar que las respuestas se mezclen con el proceso deductivo en cursiva (*itálica*) y para que los saludos cotidianos (*"Hola"*) respondan en **0.1 segundos** sin demora innecesaria de pensamiento:

Ve a **Espacio de Trabajo ➔ Modelos ➔ `local/google/gemma-4-E4B-it` ➔ Editar ➔ Prompt del Sistema**:

```text
Eres un asistente de inteligencia artificial con capacidad de razonamiento avanzado y uso de herramientas.

Sigue estrictamente esta estructura de dos fases en tus respuestas:

1. FASE DE PENSAMIENTO (Razonamiento Interno):
Si requieres analizar información, planificar la respuesta o procesar datos de herramientas, escribe todo tu proceso deductivo paso a paso EXCLUSIVAMENTE envuelto dentro de las etiquetas <think> y </think>.

2. FASE DE RESPUESTA FINAL (Al Usuario):
Inmediatamente después de cerrar la etiqueta </think>, escribe tu respuesta final dirigida a José Luis en español, con redacción natural, limpia y bien estructurada. Jamás incluyas la respuesta final dentro de las etiquetas de pensamiento ni continúes razonando fuera de ellas.
```

---

### C. La Doble Ventana de Tokens (Entrada vs. Salida)

En Open-WebUI existen **dos parámetros diferentes** que nunca deben confundirse:

```
+----------------------------------------------------------------------------------------------------+
|                                  VENTANAS DE TOKENS EN OPEN-WEBUI                                  |
+----------------------------------------------------------------------------------------------------+
| 1. VENTANA DE ENTRADA (Context Length / Contexto Total):                                           |
|    - Ubicación: Ajustes Generales del Modelo (Espacio de Trabajo).                                 |
|    - Función: Define cuánto puede LEER el modelo (Historial de chat + PDFs adjuntos + RAG).        |
|    - Valor Recomendado: 65,536 tokens.                                                             |
+----------------------------------------------------------------------------------------------------+
| 2. VENTANA DE SALIDA (max_tokens / Presupuesto de Generación):                                     |
|    - Ubicación: Menú de Chat ➔ Panel lateral "Controles" (o Parámetros Avanzados del Modelo).      |
|    - Función: Define cuánto puede ESCRIBIR el modelo en una única respuesta o llamada a tool.      |
|    - Valor por Defecto: 2,048 tokens (Insuficiente para documentos extensos).                      |
|    - Valor Recomendado: 16,384 a 65,536 tokens.                                                   |
+----------------------------------------------------------------------------------------------------+
```

> [!WARNING]
> Si deseas que el modelo redacte o convierta documentos completos de 3 o más páginas en PDF mediante herramientas, **debes elevar el deslizador `max_tokens` en el panel Controles del chat a `16384` o más**. De lo contrario, el JSON de la herramienta se cortará al token 2014 arrojando el error `Unterminated string`.

---

## 3. Catálogo de Herramientas Personalizadas (Custom Tools)

Para instalar cualquiera de estas herramientas en Open-WebUI:
1. Ve a **Espacio de Trabajo (Workspace)** ➔ **Herramientas (Tools)** ➔ **+ (Crear Herramienta)**.
2. Pega el código Python correspondiente.
3. Haz clic en **Guardar**.
4. Haz clic en el icono de engranaje ⚙️ (*Valves*) de la herramienta para configurar la URL y tu API Key.

---

### Herramienta 1: Búsqueda y Lectura RAG Teccam (LanceDB)
> Archivo fuente: [`tools/openwebui_rag_tool.py`](tools/openwebui_rag_tool.py)

Permite buscar fragmentos jurídicos/operativos y obtener textos íntegros 1:1 de documentos extensos indexados en LanceDB con vectores 1024D (Qwen3) y BM25.

```python
"""
title: Búsqueda y Lectura RAG Teccam (LanceDB)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Consulta y lee documentos de la base de conocimiento documental de Teccam (Constitución Nacional, Código Civil, Procedimientos Teccam, Patrones de Reingeniería, Rick Rubin) indexada en LanceDB con vectores 1024D (Qwen3) y BM25.
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 2.0.0
license: MIT
"""

import os
import requests
from typing import Optional, List, Union
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        GATEWAY_URL: str = Field(
            default="https://tech-support.com.ar:19000",
            description="URL base del Gateway de la suite vLLM (ej: http://127.0.0.1:8000 o https://tech-support.com.ar:19000)."
        )
        API_KEY: str = Field(
            default="vllm_key_e60d46d030d5e0c36122a064e23723a572ad9a9d",
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
        parte: int = 1
    ) -> str:
        """
        Obtiene el texto completo o una parte masiva de un documento, procedimiento o libro oficial de Teccam para redactar resúmenes integrales, síntesis ejecutivas o análisis normativos exhaustivos sin omitir pasos ni incisos.
        Acepta tanto el doc_id hexadecimal como el título exacto o parcial del procedimiento/libro.
        :param doc_id: ID único del documento (ej: '67b2111008223c9b3c3e5608') o el título del documento (ej: 'Procedimiento General de Soporte en Puestos de Trabajo').
        :param parte: Número de parte a recuperar si es un libro extenso paginado (1 para la primera parte, 2 para la siguiente, etc.).
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

        payload = {
            "doc_id": clean_doc_id,
            "parte": clean_parte,
            "token_threshold": 60000
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=25.0)
            if response.status_code == 503:
                return "Aviso: El servicio de Base de Conocimiento RAG está temporalmente desactivado globalmente."
            if response.status_code != 200:
                return f"Error al leer el documento (HTTP {response.status_code}): {response.text}"

            data = response.json()
            titulo = data.get("titulo", "Documento")
            tema = data.get("tema", "General")
            autor = data.get("autor", "Desconocido")
            modo = data.get("modo", "completo")
            content = data.get("content", "")
            total_tokens = data.get("total_doc_tokens", 0)

            if modo == "completo":
                header_info = f"--- DOCUMENTO COMPLETO: \"{titulo}\" (Tema: {tema} | Autor: {autor} | Tokens: ~{total_tokens:,}) ---\n\n"
            else:
                parte_actual = data.get("parte_actual", 1)
                total_partes = data.get("total_partes", 1)
                header_info = (
                    f"--- DOCUMENTO EXTENSO (PARTE {parte_actual}/{total_partes}): \"{titulo}\" "
                    f"(Tema: {tema} | Tokens de esta parte: ~{data.get('tokens_en_esta_parte', 0):,} de {total_tokens:,}) ---\n"
                    f"💡 [Aviso: Para leer la siguiente parte ejecuta: leer_documento_completo(doc_id=\"{data.get('doc_id')}\", parte={parte_actual + 1})]\n\n"
                )

            return f"{header_info}{content}\n\n--- FIN DEL TEXTO SUMINISTRADO ---"
        except Exception as e:
            return f"Error de conexión con el Gateway RAG ({url}): {str(e)}"
```

---

### Herramienta 2: Generador de Documentos en PDF A4
> Archivo fuente: [`tools/openwebui_pdf_tool.py`](tools/openwebui_pdf_tool.py)

Compila archivos PDF estándar A4 en **0.05 segundos**, con formateo de fórmulas químicas (`CO2, CH4, N2O`), centrado simétrico multilínea para títulos largos y auto-limpieza de archivos con más de 24 horas de antigüedad.

```python
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
```

---

### Herramienta 3: Búsqueda Web en Vivo (Ollama Cloud)
> Archivo fuente: [`tools/openwebui_web_search_tool.py`](tools/openwebui_web_search_tool.py)

Permite al modelo realizar búsquedas en internet para responder preguntas sobre noticias de hoy, clima, cotizaciones financieras y hechos actualizados.

```python
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
```

---

### Herramienta 4: Clima y Pronóstico Extendido (OpenWeatherMap)
> Archivo fuente: [`tools/openwebui_weather_tool.py`](tools/openwebui_weather_tool.py)

Permite consultar el clima actual y el pronóstico meteorológico detallado a 5 días para cualquier ciudad del mundo, con cálculo de amanecer/atardecer y ajuste de zona horaria local.

```python
"""
title: Consulta de Clima y Pronóstico (OpenWeatherMap)
author: Jose Luis Villaronga
author_url: https://github.com/JoseLVillaronga/tech-vllm
git_url: https://github.com/JoseLVillaronga/tech-vllm
description: Consulta de clima actual y pronóstico extendido a 5 días con ajuste automático de zona horaria IANA para cualquier ciudad del mundo.
required_open_webui_version: 0.3.0
requirements: requests, pydantic
version: 1.2.0
license: MIT
"""

import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pydantic import BaseModel, Field

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


class Tools:
    class Valves(BaseModel):
        OPENWEATHER_API_KEY: str = Field(
            default="TU_OPENWEATHER_API_KEY_AQUI",
            description="API Key de OpenWeatherMap (obtenida gratis en https://openweathermap.org/api)"
        )
        DEFAULT_TIMEZONE: str = Field(
            default="America/Argentina/Buenos_Aires",
            description="Zona horaria IANA por defecto para horas de salida/puesta del sol y fechas (ej: 'America/Argentina/Buenos_Aires', 'America/Montevideo', 'Europe/Madrid', o 'auto')"
        )
        DEFAULT_UNITS: str = Field(
            default="metric",
            description="Unidades de medida: 'metric' (Celsius), 'imperial' (Fahrenheit)"
        )
        DEFAULT_LANG: str = Field(
            default="es",
            description="Idioma de las descripciones (ej: 'es', 'en')"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _format_timestamp(self, ts: Optional[int], city_tz_offset: int = 0) -> str:
        if not ts:
            return "N/D"
        tz_setting = str(self.valves.DEFAULT_TIMEZONE).strip()
        if tz_setting.lower() == "auto":
            tz = timezone(timedelta(seconds=city_tz_offset))
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
            return dt.strftime("%H:%M:%S")
        if ZoneInfo:
            try:
                tz = ZoneInfo(tz_setting)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
                return dt.strftime("%H:%M:%S")
            except Exception:
                pass
        tz = timezone(timedelta(seconds=city_tz_offset))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
        return dt.strftime("%H:%M:%S")

    def _format_date(self, ts: Optional[int], city_tz_offset: int = 0) -> str:
        if not ts:
            return ""
        tz_setting = str(self.valves.DEFAULT_TIMEZONE).strip()
        if tz_setting.lower() != "auto" and ZoneInfo:
            try:
                tz = ZoneInfo(tz_setting)
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        tz = timezone(timedelta(seconds=city_tz_offset))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(tz)
        return dt.strftime("%Y-%m-%d")

    def get_current_weather(self, city: str, country_code: Optional[str] = None) -> str:
        """
        Obtiene el clima actual y el reporte detallado del día de hoy para una ciudad o localidad.
        :param city: Nombre de la ciudad o localidad (ej: 'Buenos Aires', 'San Nicolas', 'Madrid', 'Rosario').
        :param country_code: Código ISO de dos letras del país opcional (ej: 'AR', 'ES', 'UY', 'CL').
        :return: Resumen detallado del clima de hoy con mínimas, máximas, sensación térmica, viento, humedad, amanecer y atardecer en hora local.
        """
        clean_city = str(city).strip() if city and not str(type(city)).endswith("FieldInfo'>") else ""
        clean_country = str(country_code).strip() if country_code and not str(type(country_code)).endswith("FieldInfo'>") else None

        query = f"{clean_city},{clean_country}" if clean_country else clean_city
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": query,
            "units": str(self.valves.DEFAULT_UNITS),
            "lang": str(self.valves.DEFAULT_LANG),
            "appid": str(self.valves.OPENWEATHER_API_KEY)
        }

        try:
            response = requests.get(url, params=params, timeout=10.0)
            if response.status_code == 404:
                return f"Error: No se encontró la ciudad '{clean_city}'. Verifica el nombre o especifica el país."
            response.raise_for_status()
            data = response.json()

            city_tz_offset = data.get("timezone", 0)
            sunrise_ts = data.get("sys", {}).get("sunrise")
            sunset_ts = data.get("sys", {}).get("sunset")

            sunrise_str = self._format_timestamp(sunrise_ts, city_tz_offset)
            sunset_str = self._format_timestamp(sunset_ts, city_tz_offset)

            clima_info = {
                "ciudad": data.get("name"),
                "pais": data.get("sys", {}).get("country"),
                "temperatura_C": data.get("main", {}).get("temp"),
                "sensacion_termica_C": data.get("main", {}).get("feels_like"),
                "temp_min_C": data.get("main", {}).get("temp_min"),
                "temp_max_C": data.get("main", {}).get("temp_max"),
                "humedad_pct": data.get("main", {}).get("humidity"),
                "presion_hPa": data.get("main", {}).get("pressure"),
                "viento_ms": data.get("wind", {}).get("speed"),
                "estado_cielo": data.get("weather", [{}])[0].get("description", "N/D"),
                "amanecer": f"{sunrise_str} (hora local)",
                "atardecer": f"{sunset_str} (hora local)"
            }
            return f"Clima actual y reporte de hoy en {clima_info['ciudad']} ({clima_info['pais']}):\n" + "\n".join(f"- {k}: {v}" for k, v in clima_info.items())
        except Exception as e:
            return f"Error al consultar el clima actual: {str(e)}"

    def get_weather_forecast(self, city: str, country_code: Optional[str] = None) -> str:
        """
        Obtiene el pronóstico meteorológico extendido para los próximos 5 días de una ciudad o localidad.
        :param city: Nombre de la ciudad o localidad (ej: 'Buenos Aires', 'San Nicolas', 'Cordoba').
        :param country_code: Código ISO de dos letras del país opcional (ej: 'AR', 'ES', 'MX').
        :return: Pronóstico agrupado día por día con temperaturas mínimas, máximas y estado del tiempo.
        """
        clean_city = str(city).strip() if city and not str(type(city)).endswith("FieldInfo'>") else ""
        clean_country = str(country_code).strip() if country_code and not str(type(country_code)).endswith("FieldInfo'>") else None

        query = f"{clean_city},{clean_country}" if clean_country else clean_city
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": query,
            "units": str(self.valves.DEFAULT_UNITS),
            "lang": str(self.valves.DEFAULT_LANG),
            "appid": str(self.valves.OPENWEATHER_API_KEY)
        }

        try:
            response = requests.get(url, params=params, timeout=10.0)
            if response.status_code == 404:
                return f"Error: No se encontró la ciudad '{clean_city}' para el pronóstico."
            response.raise_for_status()
            data = response.json()

            city_tz_offset = data.get("city", {}).get("timezone", 0)
            daily_data = defaultdict(list)
            for item in data.get("list", []):
                ts = item.get("dt")
                date_str = self._format_date(ts, city_tz_offset) if ts else item.get("dt_txt", "")[:10]
                if date_str:
                    daily_data[date_str].append(item)

            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            resumen_dias = []

            for date_str, items in list(daily_data.items())[:5]:
                temps = [it.get("main", {}).get("temp") for it in items if it.get("main", {}).get("temp") is not None]
                min_t = min(temps) if temps else "N/D"
                max_t = max(temps) if temps else "N/D"
                climas = [it.get("weather", [{}])[0].get("description", "") for it in items]
                clima_freq = max(set(climas), key=climas.count) if climas else "N/D"
                try:
                    dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    dia_nombre = dias_semana[dt_obj.weekday()]
                    header_fecha = f"{dia_nombre} {dt_obj.day}/{dt_obj.month}"
                except Exception:
                    header_fecha = date_str

                resumen_dias.append(f"📅 **{header_fecha} ({date_str})**: Mín: {min_t}°C | Máx: {max_t}°C | Estado: {clima_freq}")

            city_name = data.get("city", {}).get("name", clean_city)
            country = data.get("city", {}).get("country", "")
            return f"Pronóstico meteorológico extendido para {city_name} ({country}):\n\n" + "\n".join(resumen_dias)
        except Exception as e:
            return f"Error al consultar el pronóstico extendido: {str(e)}"
```

---

---

## 4. Metodología de Consulta Eficiente (Técnica del Embudo Progresivo / Scaffolding Cognitivo)

El rendimiento excepcional demostrado por modelos compactos locales (como **Gemma 4 12B-it**) en tareas complejas no depende únicamente de la arquitectura de la red, sino de la **metodología de interacción y andamiaje cognitivo (*scaffolding*) aplicada por el usuario**.

Al interactuar con modelos dotados de herramientas avanzadas (RAG Jerárquico + PDF + Web), la técnica más efectiva, elegante y rápida es el **"Embudo Progresivo de 4 Pasos"**:

```
                 METODOLOGÍA DEL EMBUDO PROGRESIVO
                 
  [ PASO 1: EXPLORACIÓN / DISCOVERY ]  ➔ "¿Qué causas de nulidad hay en contratos?"
                    │                     (Búsqueda híbrida rápida en LanceDB)
                    ▼
  [ PASO 2: MAPEO ESTRUCTURAL / GPS ]  ➔ "¿Podés facilitarme un índice del Código Civil?"
                    │                     (GPS Documental: Mapea 196 secciones / 850k tokens)
                    ▼
  [ PASO 3: EXTRACCIÓN QUIRÚRGICA ]    ➔ "Analizá en profundidad 'Capítulo X y XIV'..."
                    │                     (Extracción focalizada de ~5.7K tokens)
                    ▼
  [ PASO 4: EXPORTACIÓN EJECUTIVA ]    ➔ "Generá el informe técnico formal en PDF"
                                          (Compilación y entrega de PDF vectorial en 2 págs)
```

### 1. Paso 1: Exploración Inicial (*Discovery*)
* **Objetivo:** Descubrir qué documentos y normas existen en la base de datos sin sobrecargar la memoria.
* **Prompt Típico:** `"Busca causas de nulidad de contrato en la base de datos"`
* **Herramienta activada:** `buscar_en_base_de_conocimiento` (~25-60 ms).
* **Resultado:** Recupera 4 fragmentos altamente relevantes con sus artículos, scores y notas de GPS.

### 2. Paso 2: Mapeo Estructural con GPS Documental (*Scaffolding*)
* **Objetivo:** Darle al modelo la visión panorámica de la obra para que sepa qué capítulos existen antes de leer a ciegas.
* **Prompt Típico:** `"¿Podés facilitarme un índice o la estructura del Código Civil?"`
* **Herramienta activada:** `obtener_estructura_documento(doc_id="...")`.
* **Resultado:** Mapea las 196 secciones detectadas y produce un índice temático ordenado sin saturar la ventana de contexto.

### 3. Paso 3: Extracción Quirúrgica por Sección (*Deep-Dive*)
* **Objetivo:** Descargar y razonar únicamente sobre los capítulos relevantes identificados en el Paso 2.
* **Prompt Típico:** `"Analizá en profundidad la sección de Separación y Divorcio haciendo énfasis en nulidad matrimonial..."`
* **Herramienta activada:** `leer_documento_completo(doc_id="...", seccion="Capítulo X: ..., Capítulo XIV: ...")`.
* **Resultado:** Inyección limpia de ~5.700 tokens específicos (en vez de 850.000 tokens) con latencias mínimas.

### 4. Paso 4: Exportación y Entrega Formal (*Executive Output*)
* **Objetivo:** Formalizar el análisis en un documento exportable corporativo.
* **Prompt Típico:** `"Sí, por favor, genera el informe ejecutivo en PDF"`
* **Herramienta activada:** `generate_pdf_document`.
* **Resultado:** PDF de 2 páginas con formato vectorial A4, tipografía institucional y enlace de descarga.

> 📘 **Evidencia y Registro de Prueba de Campo:**  
> Podés consultar las transcripciones completas de estas pruebas empíricas en:
> * [`docs/pruebas_campo/prueba_campo_rag_jerarquico_v2_2026-09-01.md`](docs/pruebas_campo/prueba_campo_rag_jerarquico_v2_2026-09-01.md) (Flujo completo de 3 pasos)
> * [`docs/pruebas_campo/prueba_campo_62k_matrimonio_pdf_2026-09-01.md`](docs/pruebas_campo/prueba_campo_62k_matrimonio_pdf_2026-09-01.md) (Digestión masiva de 59.3K tokens y compilación PDF)

---

## 5. Flujos de Trabajo Combinados (Casos Prácticos)

### Flujo 1: Búsqueda RAG ➔ Lectura Completa ➔ Exportación a PDF de 2 Páginas
1. **Pregunta:** *"Hablemos del procedimiento de soporte en Teccam"*
   * *Acción del LLM:* Invoca `buscar_en_base_de_conocimiento("Procedimiento General de Soporte en Teccam")`.
   * *Resultado:* Recupera los 4 fragmentos iniciales con su `doc_id: 67b2111008223c9b3c3e5608`.
2. **Petición de Síntesis:** *"Pasame el documento completo en PDF"*
   * *Acción del LLM:* Invoca `leer_documento_completo(doc_id="67b2111008223c9b3c3e5608")`.
   * *Resultado:* Obtiene los 19 fragmentos íntegros (1.279 tokens).
   * *Acción del LLM:* Redacta el Markdown y llama a `generate_pdf_document`.
   * *Resultado:* Genera un PDF ejecutivo de **2 páginas** con enlace de descarga directa en **0.05 segundos**.

---

### Flujo 2: Búsqueda Web en Vivo ➔ Resumen Científico ➔ PDF
1. **Pregunta:** *"Haceme un resumen sobre cambio climático basado en el IPCC y pasamelo en PDF"*
   * *Acción del LLM:* Invoca `buscar_en_internet("resumen completo y actualizado sobre el cambio climatico")`.
   * *Resultado:* Extrae informes de MITECO e IPCC en tiempo real.
   * *Acción del LLM:* Compila el PDF con fórmulas químicas limpias (`CO2, CH4, N2O`).

---

## 6. Guía de Buenas Prácticas y Solución de Problemas (FAQ)

### ❓ ¿Por qué iniciar un chat limpio al pasar de un PDF adjunto a una consulta RAG?
* **Causa:** Cuando subes un archivo PDF directamente en el chat, Open-WebUI lo adjunta de forma fija y vuelve a enviar todo su texto (~8.000 tokens) en cada turno.
* **Efecto:** Si luego preguntas por procedimientos internos o leyes, el modelo intentará responder forzando el contenido del PDF adjunto o confundirá los UUIDs del chat con los IDs de LanceDB.
* **Buenas Prácticas:** Usa un hilo limpio cuando quieras consultar la base de conocimiento general RAG.

---

### ❓ ¿Por qué aparecía el error `Unterminated string starting at line 1 column 3891`?
* **Causa:** El modelo intentó escribir un documento completo de más de 1.000 palabras dentro del argumento JSON `markdown_content` de la herramienta de PDF, pero el límite `max_tokens` de salida en los **Controles del Chat** estaba en 2.048 tokens. Al llegar al token 2014, la generación se cortó por la mitad.
* **Solución:** Mover el deslizador **`max_tokens`** en el panel lateral **Controles** del chat a **`16384`** o **`65536`**.

---

### ❓ ¿Por qué aparecía el error `Object of type FieldInfo is not JSON serializable`?
* **Causa:** Ocurre cuando un argumento opcional de una herramienta de Open-WebUI se define con `Field(None, ...)` como valor por defecto. Si el modelo omite el argumento, Python le pasa el objeto interno `FieldInfo` en lugar de `None`, rompiendo `json.dumps()`.
* **Solución:** Todas las herramientas provistas en este manual están 100% blindadas con sanitización defensiva de tipos.

---

### ❓ ¿Cuánto tiempo duran los enlaces de descarga de los PDFs?
* Los archivos PDF se generan en `/home/jose/vllm/outputs/pdfs/` y cuentan con un mecanismo de **auto-limpieza TTL de 24 horas**. Cada vez que se compila un nuevo PDF, el motor elimina automáticamente los archivos que tengan más de un día de antigüedad para mantener el disco limpio.
