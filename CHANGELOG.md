# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [2.5.0] - 2026-09-04

### Added
- **5to Invariante Operativo MEA (Grounding y Humildad Epistémica):**
  - Implementada directiva obligatoria en `gateway/core/alignment_engine.py` y persistida en MongoDB: ante repreguntas sobre el alcance normativo, solicitudes de fuentes exactas o números de artículos, queda terminantemente prohibido responder de memoria o inventar rangos aproximados. El modelo está obligado a emitir una llamada a `buscar_en_base_de_conocimiento` o `obtener_estructura_documento`.
- **Re-ranking Canónico para Figuras Rectoras en LanceDB (`rag_engine.py`):**
  - Boosting definitorio (+0.06 de similitud) para fragmentos ubicados bajo *Disposiciones Generales*, *Parte General* o *Título Preliminar* cuando la consulta del usuario incluye términos definitorios (*"definición"*, *"concepto"*, *"qué es"*).
  - Elevó al Artículo 957 (Definición de Contrato) del Puesto #10 al Puesto #1 indiscutido (88.41% de similitud) en la primera llamada de búsqueda semántica.
- **Soporte de Proyector Multimodal Opt-in en `llama-srv.sh`:**
  - Lógica configurable para proyectores multimodales `--mmproj` respetando `LLAMA_MMPROJ_PATH`. Por defecto deshabilitado para garantizar inferencia de texto pura sin interferencias de tensores visuales en modelos densos.
- **Botón de Configuración Rápida para Gemma 4 12B en Dashboard Web (`tab_config.html` y `dashboard_core.js`):**
  - Botón de 1 clic `⚡ Gemma 4 12B (Denso / VRAM Baja)` que carga automáticamente los parámetros óptimos medidos en campo (`131k ctx`, `batch 4096`, `ubatch 1024`, `gpu 999`, `moe 0`, `reasoning off`, `mlock`, `threads 8`).
  - Incorporado campo editable `LLAMA_DIR` en la interfaz para máxima portabilidad (respetando el 4to Invariante MEA).
- **Sincronización Canónica de Invariantes MEA en la GUI (`dashboard_alignment.js`):**
  - Sincronizada la constante `CANONICAL_INVARIANTS_PROMPT` con los 5 invariantes operativos completos, garantizando que el botón *"Restaurar Invariantes Canónicos"* restablezca el 5to invariante (Grounding y Humildad Epistémica) de forma resiliente.
- **Análisis de Concurrencia Multi-Usuario en Oficina (`docs/INTEGRACION_LLAMACPP_Y_QWEN_MOE.md`):**
  - Documentada la comparativa de riesgo entre *Multi-Slot Estático (`--parallel N`)* vs *Cola Serializada Dinámica (FIFO por defecto, `--parallel 1`)*, ratificando la cola FIFO como diseño canónico para preservar el 100% de los 131.072 tokens por consulta sin riesgo de truncamiento ni colapso de contexto.

### Fixed
- **Descontaminación de Citas en Encabezados Jerárquicos (`app_rag_sync.py`):**
  - Eliminación previa de enlaces Markdown `[...](...)` y corchetes doctrinarios antes de evaluar la longitud del título en `detect_heuristic_header`.
  - Reparado `TITULO II Contratos en general` en el Código Civil y Comercial, el cual era descartado por superar 120 caracteres debido a citas bibliográficas pegadas al OCR.
- **Bucle de Token `<unused49>` en Gemma 4 12B:**
  - Resuelto el conflicto de inicio de turnos y tokens de control al desactivar el razonamiento en modo texto puro sin el proyector de visión cargado.
  - Consumo estabilizado en 17.7 GB de VRAM (con 6.3 GB libres en RTX 3090) a 60 tokens/segundo sostenidos.
- **Liberación de Herramientas Jerárquicas en Open-WebUI (`tools/openwebui_rag_tool.py`):**
  - Eliminada la prohibición textual que impedía al LLM invocar `obtener_estructura_documento` en consultas de definición.
  - Aumentado `DEFAULT_TOP_K` a 5.

## [2.4.0] - 2026-09-03

### Added
- **Optimización de Chunking Jerárquico en LanceDB (`app_rag_sync.py`):**
  - Desempaquetado de pseudo-tablas de OCR (`unpack_pseudo_tables`): desarticula tablas de grilla masivas (>1.500 caracteres) presentes en documentos legales complejos como el Código Civil y Comercial (CCCN), restituyendo saltos de línea estructurales.
  - Detección heurística multicriterio de encabezados (`detect_heuristic_header`): soporte para niveles jerárquicos 1 (Libros/Partes), 2 (Títulos), 3 (Capítulos/Secciones), 4 (Artículos normativos) y encabezados en negrita sin prefijo Markdown.
  - Subdivisión acotada segura (*Bounded Chunks*): garantiza que ninguna fila o párrafo exceda `max_chars` (1.100 caracteres ~ 220 tokens), dividiendo por oraciones.
  - Purga determinista previa: eliminación asegurada de registros anteriores (`table.delete(doc_id)`) antes de insertar nuevos chunks para prevenir duplicaciones al re-indexar con `--force`.
- **Búsqueda Focalizada y Boosting Normativo (`rag_engine.py`):**
  - Parámetro opcional `doc_id` / `documento_id` en `search_knowledge_base` para acotar la búsqueda a una obra específica.
  - Boosting léxico normativo: incremento de similitud (+0.35 si la sección coincide con el artículo buscado, +0.25 si el fragmento empieza con el artículo).
  - Coincidencia flexible de temas con SQL `LIKE '%...'` para que consultas con `dominios="Derecho"` coincidan correctamente con `"Derecho Argentino"`.
- **Protección Anti-Desbordamiento en GPS Documental (`rag_engine.py`):**
  - Límite de seguridad `MAX_GPS_ROWS = 50` con advertencia de granularidad en `get_document_structure`, reduciendo el payload de 667 KB a 11.9 KB (-98.3% en tokens).
  - Parámetro opcional `filtro` en `get_document_structure` para acotar el árbol a palabras clave (ej: `filtro="contrato"`).
- **Afinación de Herramientas RAG (`tools/openwebui_rag_tool.py` y `gateway/tools/rag_endpoints.py`):**
  - Soporte de `doc_id` y `filtro` en los endpoints del Gateway y en la herramienta para Open-WebUI.
  - Docstrings afinadas para orientar al LLM a priorizar `buscar_en_base_de_conocimiento` para definiciones y artículos puntuales.
- **Aceleración de Ingesta con Prefill MoE (`llama.cpp`):**
  - Parámetro `LLAMA_UBATCH_SIZE=1024` en `.env` y `llama-srv.sh` para acelerar la ingesta en GPU RTX 3090.
  - Selector reactivo de tamaño de micro-batch en el Dashboard de Configuración (`tab_config.html` y `dashboard_core.js`).
- **Inferencia Raw Gateway en Puerto 8010:**
  - Endpoint directo de inferencia sin prompts de alineación ni invariantes (preservando fecha/hora y seguridad).
  - Control granular de permisos para API Keys (8000 vs 8010).

### Fixed
- Colapso de CCCN en 2 chunks (1 hiper-chunk de 425k tokens en "Sección General"). Ahora subdividido en 3.300 fragmentos estructurados en 3.042 secciones.
- Mapeo plano de *El Príncipe* (1 sección). Ahora mapeado en 27 secciones correspondientes a sus 26 capítulos.
- Mapeo de *DNU 70/2023* (2 secciones). Ahora mapeado en 419 secciones.
- Desbordamiento de ventana de contexto en `llama-server` (293k tokens) al consultar la estructura de obras masivas en Open-WebUI.
- Comparación estricta de dominios temáticos en pre-filtrado SQL de LanceDB.
