# 🛠️ Arquitectura de Tool Calling en Modelos Mistral con llama.cpp y vLLM Gateway

> **Estado:** Implementado y Verificado en Producción  
> **Fecha:** Septiembre 2026  
> **Ámbito:** Inferencia local con `llama-server` (GGUF), `vllm-gateway` (FastAPI/Granian) y frontends OpenAI-compatibles (`Open-WebUI`).

---

## 1. Contexto y Definición del Problema Raíz

En el ecosistema de inferencia local con modelos de la familia **Mistral** (`Mistral-Small-24B`, `Mistral-Nemo-12B`, `Ministral-8B`, `Devstral`), el uso de herramientas (*tool calling* o *function calling*) en entornos interactivos multi-turno sufre de fallos sistemáticos cuando se ejecutan sobre `llama-server` y se consumen desde frontends estándar como **Open-WebUI**.

A través de pruebas empíricas y una exhaustiva investigación del estado del arte en la comunidad de código abierto, se identificaron **tres fallas estructurales encadenadas**:

```
[Cliente Open-WebUI]
        │
        ▼ (Turno 1: tools[])
 [llama-server + GGUF] ──► Falla 1: Template nativo roto (mistral-v7-tekken)
        │                 Solución: Requiere inyección de --jinja y template externo
        ▼ (Genera [TOOL_CALLS])
[Ejecución de Herramienta]
        │
        ▼ (Turno 2: Rol 'tool' devuelto)
 [llama-server] ─────────► Falla 2: Template Jinja lanza excepción 400 por ID != 9 chars
        │                 Falla 3: Modelo degrada a Bare-JSON sin [TOOL_CALLS]
        │                 llama-server lo expone como texto plano (content)
        ▼
[Frontend Open-WebUI] ──► Muestra JSON crudo al usuario en vez de ejecutar la herramienta
```

---

## 2. Investigación del Estado del Arte y Enfoques de la Comunidad

El análisis de repositorios de referencia (`ggml-org/llama.cpp`, `ollama/ollama`, `BerriAI/litellm`, `vllm-project/vllm`, `open-webui/open-webui`) demuestra que este es uno de los problemas más debatidos y peor resueltos de la industria:

### A. Fallo de IDs y Excepciones Jinja en `llama.cpp`
* **Evidencia:** [llama.cpp Issue #26359](https://github.com/ggml-org/llama.cpp/issues/26359) (*"llama-server returns a tool-call id that its own chat template then rejects (Ministral-8B, --jinja)"*) y [llama.cpp PR #14148](https://github.com/ggml-org/llama.cpp/pull/14148).
* **Causa:** La plantilla Jinja provista por Mistral AI contiene validaciones draconianas mediante `raise_exception`:
  ```jinja
  {%- if tool_call.id | length != 9 %}
      {{- raise_exception('Tool call IDs should be alphanumeric strings with length 9!') }}
  {%- endif %}
  ```
* **Impacto:** `llama-server` históricamente genera identificadores de llamada basados en timestamps Unix (13 dígitos, ej. `1697377797897`) o UUIDs (36 caracteres con guiones). Al recibir de vuelta el mensaje de la herramienta con ese ID, el validador Jinja aborta con HTTP 400 antes de iniciar el procesamiento.

### B. "Bare-JSON Tool Calls" en `ollama` y `litellm`
* **Evidencia:** [Ollama Issue #17323](https://github.com/ollama/ollama/issues/17323) (*"Bare-JSON tool call models: content generated after a tool call is silently dropped"*) y [LiteLLM PR #33037](https://github.com/BerriAI/litellm/pull/33037) (*"fix(fireworks): set finish_reason=tool_calls for content-embedded tool calls"*).
* **Causa:** Tras la ingesta de los primeros resultados de herramienta (`[/TOOL_RESULTS]`), el espacio probabilístico del modelo no vuelve a emitir el token de control `[TOOL_CALLS]`, sino que genera directamente un array JSON plano:
  ```json
  [{"name": "buscar_en_base_de_conocimiento", "arguments": {"consulta": "..."}}]
  ```
* **Impacto en `llama-server`:** El parser C++ de `llama-server` solo conmuta a `tool_calls` si halla la etiqueta textual `[TOOL_CALLS]`. Al faltar dicha etiqueta, serializa los tokens generados dentro del campo `content` del chunk SSE (`delta.content`), dejando al cliente ciego ante la invocación.

---

## 3. Análisis Crítico de las Soluciones Alternativas de la Industria

| Solución Intentada | Implementación | Limitación / Razón de Descarte |
| :--- | :--- | :--- |
| **"Cirugía" de Plantilla Jinja (Unsloth)** | Eliminar los bloques `raise_exception` en el archivo `.jinja`. | **Parche cosmético (Ley 2):** Resuelve el error 400 de inicialización, pero **no soluciona** la emisión de JSON crudo en el Turno 2, que sigue filtrándose como texto. |
| **Gramáticas GBNF Forzadas (`llama.cpp`)** | Restringir el muestreo mediante EBNF para exigir estructura JSON. | **Riesgo en bucle:** Impide al modelo redactar texto en lenguaje natural cuando ya concluyó la búsqueda, provocando alucinaciones forzadas o bucles infinitos de llamadas. |
| **Pipelines en Open-WebUI** | Crear un filtro en Python dentro del backend de Open-WebUI. | **Destruye el Streaming:** Requiere acumular todo el búfer de tokens en memoria antes de pasarlo a la UI, introduciendo latencias de varios segundos con pantalla congelada. |
| **Parsers en LangChain / LiteLLM Proxy** | Analizadores `JsonOutputToolsParser` en capa cliente. | **Dependencia de Framework:** Solo funciona si el usuario escribe código a medida; no resuelve la compatibilidad con interfaces estándar de usuario. |
| **Máquinas de Estado Dedicadas (vLLM / Ollama)** | Parsers nativos en Go o Python integrados en el binario del motor. | Inviable directamente sobre `llama-server` compilado en C++ sin alterar su código fuente upstream. |

---

## 4. Nuestra Solución: Auto-Guardia RAG de Latencia Cero en el Gateway

Siguiendo las **Leyes Universales de Ingeniería** (Ley 1: Modularidad estricta, Ley 2: Causa raíz, Ley 3: Mínimo blast radius, Ley 4: Integridad en cascada), implementamos una solución desacoplada y transparente de dos fases:

```
┌─────────────────────────────────────────────────────────────┐
│ FASE 1: Inicialización Limpia (llama-srv.sh)                │
│ • Detección automática de modelos Mistral                   │
│ • Inyección dinámica de plantilla Jinja externa verificada │
│ • Parámetros: --jinja --chat-template-file <path>           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 2: Auto-Guardia en Streaming (proxy_factory.py)        │
│                                                             │
│   Chunk inicial ──► ¿Empieza con '[' o '{'?                 │
│         │                                                   │
│         ├── NO ──► Flush inmediato (0 ms delay de streaming)│
│         │                                                   │
│         └── SÍ ──► Retención especulativa (buffer mínimo)   │
│                      │                                      │
│                      ▼                                      │
│              parse_raw_tool_calls()                         │
│              • Valida contra valid_tool_names autorizadas   │
│              • Convierte Bare-JSON a delta.tool_calls SSE   │
│              • finish_reason="tool_calls"                   │
└─────────────────────────────────────────────────────────────┘
```

### Componentes de la Arquitectura:

1. **Resolución Portable de Plantillas ([`llama-srv.sh`](../llama-srv.sh)):**
   - Resuelve rutas dinámicamente mediante variables de entorno normalizadas.
   - Detecta si el modelo activo es de la familia Mistral e inyecta la plantilla oficial correspondiente con soporte `--jinja`.

2. **Parser Especializado ([`gateway/core/tool_governor.py`](../gateway/core/tool_governor.py)):**
   - Función pura `parse_raw_tool_calls(text, valid_tools)`.
   - Soporta tanto arrays JSON planos (`[{"name": ..., "arguments": ...}]`) como formatos pseudotokenizados con corchetes (`[fn_name[CALL_ID]...[ARGS]...]`).
   - Genera IDs sintéticos que cumplen la restricción de 9 caracteres alfanuméricos (`call_` + 8 caracteres hex).

3. **Intercepción de Flujo en Tiempo Real ([`gateway/proxy/proxy_factory.py`](../gateway/proxy/proxy_factory.py)):**
   - **Cero latencia para respuestas normales:** Si los primeros caracteres no coinciden con un token de apertura estructural (`[` o `{`), el generador SSE libera el flujo instantáneamente sin tocarlo.
   - **Grounding perentorio:** Solo promueve a tool call si el nombre de la función pertenece al conjunto de herramientas válidas declaradas en la petición (`valid_tool_names`). Si el modelo simplemente estaba citando un fragmento de código JSON para explicarlo al usuario, el texto fluye de manera natural sin corromperse.

---

## 5. Estudio de Caso Real: Consulta "Tratado Antártico y Ley de Glaciares"

Durante las pruebas de campo en `Open-WebUI`, se evaluó la consulta:
> *"Analiza la relacion entre el tatado antartico y la ley de proteccion de glaciares"*

### Telemetría Registrada del Evento:
* **Comportamiento en Turno 1:** El modelo emitió una ráfaga paralela de **27 llamadas a herramientas** en un único turno.
* **Resolución LanceDB:** Las 27 búsquedas se ejecutaron concurrentemente en ~190 ms promedio por búsqueda.
* **Contexto Ingerido:** 108 fragmentos documentales recuperados (**52.271 tokens de prompt**).
* **Procesamiento de Prompt:** `llama-server` procesó los 52K tokens en **48,7 segundos** (`prompt_ms: 48738`).
* **Generación de Respuesta:** **21,0 segundos** (`predicted_ms: 21051`).
* **Resultado Jurídico:** Identificación exacta y fundamentada del **Artículo 16 de la Ley 26.639** (que supedita expresamente el régimen de glaciares en el Sector Antártico al Tratado Antártico y su Protocolo Ambiental) y la **Ley 15.802** (ratificación del Tratado de Washington).

### Diagnóstico de la Ráfaga Paralela y Resolución Implementada:
* **Fortaleza Comprobada:** El stack (Gateway + llama-server + LanceDB + Open-WebUI) demostró estabilidad absoluta: no hubo desbordamientos de búfer, pérdidas de conexión ni corrupciones de memoria ante una carga masiva de 52K tokens en un solo turno.
* **Diagnóstico de Redundancia:**
  El modelo generó variantes de consulta idénticas o casi idénticas de forma redundante:
  - `"tratado antartico ley de glaciares"` (repetida 6 veces)
  - `"tratado antartico"` (repetida 4 veces)
  - `"ley 26639"` (repetida 4 veces)
* **Solución Implementada: Deduplicador Perimetral de Consultas Idénticas:**
  Siguiendo la directiva de respetar el *polimorfismo válido* de Mistral (permitiendo múltiples búsquedas semánticas concurrentes sin limitar arbitrariamente la cantidad total de llamadas distintas), se incorporó el sistema de deduplicación determinista:
  1. **Normalización Canónica (`normalize_tool_call_signature`):** Compara llamadas ignorando el orden de claves en JSON, espacios accidentales y diferencias de mayúsculas en los argumentos.
  2. **Deduplicación en Streaming y No-Streaming (`proxy_factory.py`):** Intercepta la ráfaga emitida por el modelo; si existen llamadas idénticas, descarta los duplicados y re-emite únicamente las llamadas únicas limpiamente indexadas hacia `Open-WebUI`.
  3. **Pruning Defensivo en Entrada (`tool_governor.py`):** Si un historial de conversación contiene llamadas duplicadas en el turno activo, purga las llamadas redundantes y sus correspondientes respuestas de rol `tool` antes de enviar el prompt a `llama-server`.
  4. **Impacto:** Reduce el volumen de prompt hasta en un ~75% en ráfagas repetitivas, recortando drásticamente el tiempo de KV cache y preservando el 100% de la riqueza semántica explorada por el LLM.

---

## 6. Validación de Polimorfismo Válido y Equilibrio Hardware/Software

En una prueba posterior con la misma temática, el modelo demostró la validez de no imponer topes ciegos a llamadas distintas:
* **Descomposición en 4 Dimensiones Ortogonales:** En un único turno emitió 4 búsquedas paralelas independientes:
  1. `"Relación entre Tratado Antártico y ley de protección de glaciares en Argentina"`
  2. `"Ley de glaciares 26639"`
  3. `"Tratado Antártico"`
  4. `"Definición de glaciar"`
* **Comportamiento del Deduplicador:** Como ninguna llamada era idéntica, el Gateway descartó 0 llamadas. Las 4 búsquedas se resolvieron concurrentemente en LanceDB en ~160 ms promedio.
* **Resultado:** Contexto acotado en **13.121 tokens de prompt**, procesado en 9.1 segundos, produciendo una síntesis legal de máxima calidad con citas estructuradas.

### Dimensionamiento Físico de la Ventana de Contexto (88K) y Gestión de VRAM:
* **Límite Teórico vs Realidad Operativa:** El modelo soporta teóricamente 128k tokens, pero en una GPU de 24 GB (RTX 3090) esto dejaba el margen de VRAM en ~98% (23.5 GB), con riesgo de fallo por fragmentación de memoria en CUDA.
* **Ajuste a 88k:** Dado que el `Tool Governor` y el `Context Pruner` imponen por software un techo máximo de ~55k-60k tokens por turno, la ventana física en `llama-server` fue dimensionada a **88.000 tokens**.
* **Métricas en Producción:**
  - Colchón de seguridad: **~28.000 tokens de margen** entre el software y el hardware.
  - Consumo de VRAM: **20.5 GB / 24.0 GB (85.37%)**.
  - Margen libre de VRAM: **~3.5 GB**, erradicando OOMs por picos de asignación de atención y permitiendo operación 24/7 sin reinicios de servicio.
