# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

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
