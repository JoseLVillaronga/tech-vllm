# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [2.11.0] - 2026-09-08

### Added
- **Modo de Alineación Agéntico en Puerto 8010 (`gateway/core/alignment_engine.py`, `gateway/server.py`):**
  - Implementación de `alignment_mode="agentic"` para suites de benchmarking y agentes de desarrollo (Deepseek Harness, SWE-bench).
  - Preservación 100% virgen del System Prompt y de las instrucciones de usuario (sin inyección de directivas doctrinales ni prefijos invasivos), garantizando compatibilidad absoluta con plantillas de evaluación estándar.
- **Escudo Atencional Bilingüe y Agnóstico al Dominio (`gateway/core/alignment_engine.py`):**
  - Incorporada heurística léxica (`is_english_query`) para detectar automáticamente el idioma de la tarea.
  - Inyección perentoria de anclaje contextual al pie de respuestas de herramientas (`role: "tool"`) en inglés o español, enfocado exclusivamente en la tarea activa y libre de menciones sectoriales o legales accidentales.
- **Sanitización Robusta de Nombres de PDF (`pdf_engine.py`, `tools/openwebui_pdf_tool.py`):**
  - Implementación de `sanitize_pdf_filename`: convierte barras (`/`, `\`) en guiones bajos (`_`) en títulos normativos o fechas (ej: `Decreto 1030/2020` -> `decreto_1030_2020.pdf`), erradicando errores de sistema de archivos (`[Errno 2] No such file or directory`).
  - Protección estricta contra secuencias de *path traversal* (`..`) y caracteres inválidos para sistemas de archivos multiplataforma.

### Changed
- **Resolución Dinámica de Rutas de Almacenamiento PDF (`pdf_engine.py`):**
  - Erradicación de ruta absoluta hardcodeada (`PDF_STORAGE_DIR = "/home/jose/vllm/outputs/pdfs"`), sustituida por resolución dinámica relativa al directorio raíz del proyecto (`outputs/pdfs`), en cumplimiento del Invariante MEA de Portabilidad y Prohibición de Rutas Absolutas.
- **Parametrización de Modos en Fábrica de Proxies (`gateway/proxy/proxy_factory.py`):**
  - `create_proxy_app` ahora admite `alignment_mode: Optional[str] = None` (`full`, `agentic`, `off`), con retrocompatibilidad garantizada con el parámetro booleano `include_alignment`.

### Documented
- **Prueba de Campo Agéntica en Deepseek Harness (`docs/pruebas_campo/prueba_campo_deepseek_harness_agentic_gpt_oss_20b_2026-09-08.md`):**
  - Evaluación forense de 13 turnos, 55 pasos y 42 llamadas a herramientas ejecutando el desarrollo autónomo de un portal corporativo en Flask con persistencia real en MongoDB.
  - Comparativa de rendimiento: `gpt-oss-20b` completó la tarea en **~35 minutos** (6x más rápido) frente a las **3.5 horas** requeridas por `Qwen 35B`.
  - Documentación de auto-reparación de tracebacks de Python (`ValueError` y `TemplateNotFound`) y coronación formal de `gpt-oss-20b` como el modelo rector para RAG intensivo y flujos agénticos en el cluster local.

## [2.10.0] - 2026-09-07

### Added
- **Recordatorio Dinámico de Foco Activo Intra-Turno (`gateway/core/alignment_engine.py`):**
  - Inyección perentoria de anclaje contextual (`📌 [RECORDATORIO DE FOCO ACTIVO]`) en la última respuesta de herramienta del turno (`messages[-1]["role"] == "tool"`).
  - Ancla directamente el requerimiento del usuario a 0 tokens de distancia del bloque `<think>`, neutralizando la atenuación atencional (*In-Turn Attention Decay*) y el secuestro atencional (*Attention Crosstalk*) inducido por tokens incidentales en ciclos multi-herramienta extensos.
  - Invariante 8 formalizado en el motor de alineación y sincronizado con MongoDB `db.alignment_settings`.
- **Vaciado Físico Asíncrono de Slots KV Cache (`gateway/core/slot_flusher.py`, `llama-srv.sh`):**
  - Implementación del módulo `slot_flusher.py` para invocar asíncronamente `POST /slots/{id}?action=erase` contra `llama-server` ante eventos de poda de contexto o colisiones de prefijo.
  - Inclusión de `--parallel 2` y `--slot-save-path "${PROJECT_DIR}/scratch/slots"` en `llama-srv.sh` habilitando control granular de slots y persistencia física en disco sin saturación de RAM.
  - Inyección de `cache_prompt: false` en los payloads JSON podados para invalidar prefijos corruptos o viciados en el motor de inferencia.

### Changed
- **Calibración Matemática de Poda y Compactación Selectiva de Contexto (`gateway/core/context_pruner.py`):**
  - Ajuste del factor de estimación léxica de tokens para español técnico y serialización JSON a 2.8 caracteres por token, con un overhead basal de 5.000 tokens reservados para esquemas de herramientas y system prompt.
  - Reducción del límite de ventana deslizante a 6 turnos atómicos de usuario (`CONTEXT_PRUNER_MAX_TURNS=6`) y techo de 32.000 tokens (`CONTEXT_PRUNER_MAX_TOKENS=32000`).
  - Compactación selectiva de respuestas previas del asistente anteriores a los últimos 2 turnos: condensación a los primeros 300 caracteres (párrafo rector) y sustitución del contenido extenso por marcador de resumen, suprimiendo atractores semánticos masivos sin quebrar el hilo conversacional.
- **Resolución de Filtrado Cruzado y Fallback Abierto en RAG (`rag_engine.py`):**
  - Expansión de la cláusula de pre-filtrado SQL en LanceDB: búsqueda insensible a mayúsculas/minúsculas y acentos sobre `doc_topic` y cruzada contra `doc_title` (`(lower(doc_topic) LIKE '%{tema}%' OR lower(doc_title) LIKE '%{tema}%')`).
  - Implementación de mecanismo de *fallback* automático a búsqueda abierta no restringida si el pre-filtrado por dominio o título devuelve 0 candidatos, erradicando fallos silenciosos de recuperación causados por divergencias de taxonomía en el LLM (Ley 4).

### Documented
- **Prueba de Campo de 31 Turnos de Estrés (`docs/pruebas_campo/prueba_campo_anti_crosstalk_y_foco_dinamico_2026-09-07.md`):**
  - Auditoría forense exhaustiva de 31 turnos sin un solo colapso de atención ni alucinación cruzada (*0% failure rate*).
  - Mantenimiento constante de velocidad de prefill a ~4.500 tok/s en turnos avanzados (>25 turnos) gracias a la poda calibrada.
  - Validación de honestidad epistémica radical ante preguntas capciosas de derecho tributario (impuesto PAIS inmobiliario) y recuperación exhaustiva de los 28 artículos del Título I del Libro II del Código Penal.
- **Retrospectiva de Sesión (`docs/RETROSPECTIVAS_SESIONES.md`):**
  - Registro de la sesión nocturna del 2026-09-07 con análisis de causas raíz, lecciones aprendidas sobre falsas hipótesis de discrepancia léxica vs SQL pre-filters, y auditoría de RVI (0.0/10).

## [2.9.0] - 2026-09-06

### Added
- **Extractor y Jerarquizador Normativo InfoLEG a Markdown (`scripts/fetch_infoleg.py`, `docs/MANUAL_EXTRACTOR_INFOLEG.md`):**
  - Implementación de `InfoLegFetcher` con resolución transparente de URLs directas (`norma.htm`, `texact.htm`), páginas de carátula (`verNorma.do?id=...`) o IDs numéricos, con priorización automática de texto actualizado frente al texto original histórico.
  - Evasión de bloqueo `403 Forbidden` de Apache InfoLEG mediante cabecera canónica `User-Agent` de escritorio.
  - Extracción de metadatos oficiales (Boletín Oficial, fecha, tipo de norma, organismo emisor y resumen oficial) e inyección estructurada en el encabezado del documento Markdown.
  - Normalización forzada bajo codificación `windows-1252`, preservando ordinales normativos (`1°`, `2°`, `10°`), guiones largos (`—`) y comillas tipográficas.
  - Implementación de `InfoLegParser` para depuración de boilerplate (scripts, estilos, banners `#branding`, menús y mapas web), preservación de bloques formales de párrafo y conversión de tablas HTML a tablas Markdown GFM.
  - Estructuración legal multinivel `# Título`, `## Libro/Parte`, `### Título/Visto/Considerando`, `#### Capítulo`, `##### Sección`, y articulado `**ARTÍCULO X°.- Epígrafe.**` 100% compatible con la función `detect_heuristic_header` de LanceDB (`app_rag_sync.py`).
  - Soporte para ejecución en modo interactivo asistido por consola y modo desatendido por argumentos CLI (`--url`, `--title`).
  - Validación de extracción en 3 normativas de prueba en `scripts/output/`: Ley 26.639 (Glaciares, 18 artículos), Decreto 70/2025 (Estructura Organizativa, 14 artículos) y Código Civil y Comercial de la Nación (2.713 artículos continuos).
  - Manual técnico y guía de usuario completa en [`docs/MANUAL_EXTRACTOR_INFOLEG.md`](docs/MANUAL_EXTRACTOR_INFOLEG.md) y [`scripts/README.md`](scripts/README.md).

## [2.8.0] - 2026-09-06

### Added
- **Reescalado Adaptativo 2D por Dimensión y Área Mínima (`gateway/tools/vision.py`):**
  - Implementado doble umbral de disparo: $\min(w, h) < 512$ o $w \cdot h < 262.144 \text{ px}^2$, garantizando densidad de parches espaciales en el ViT de Qwen2.5-VL para muestras pequeñas, recortes o formatos panorámicos.
  - Corrección de truncamiento en punto flotante usando `round` para asegurar cumplimiento exacto de la cota mínima de resolución.
  - Cobertura de pruebas unitarias automatizadas (`test_optimize_image_resolution_for_vit` en `tests/test_gateway_tools.py`).
- **Prompt Estructurado de Visión en 2 Fases (`gateway/tools/vision.py`):**
  - Reemplazo de directivas conversacionales por una estructura imperativa en dos bloques:
    1. *Transcripción y Datos* (OCR exhaustivo de textos, números y tablas).
    2. *Descripción Visual* (análisis de componentes, diagramas, figuras y colores).
  - Eliminación de falsos rechazos (*safety refusals*) de Qwen2.5-VL en español, logrando extracción íntegra de comprobantes y números de remito en un único pase de ~4.5s en CPU/RAM.
- **Universalidad Multi-Modelo y Eficiencia Radical de Contexto (`docs/ARQUITECTURA_MULTIMODAL_DESACOPLADA_RAM_CPU.md`, `MANUAL_OPENWEBUI.md`):**
  - Documentación formal del desacoplamiento: cualquier modelo de texto puro local (Gemma 4, Qwen 2.5 32B/35B, GLM-4.7-Flash MoE, etc.) queda dotado de visión de alta fidelidad sin requerir proyector `mmproj` ni consumir VRAM.
  - Destilación semántica en texto estructurado con ahorro del 85% al 95% de la ventana de contexto en la GPU frente a proyectores visuales nativos o Base64.
- **Mitigación de Sesgo de Anclaje RAG y Re-búsqueda Iterativa (`gateway/core/alignment_engine.py`, `tools/openwebui_rag_tool.py`):**
  - Incorporado el Principio 6 en las Directivas Fundamentales MEA: evaluación crítica de pertinencia causal directa y prohibición de anclaje forzado de figuras contractuales o accesorias que no regulan el caso consultado.
  - Reemplazo del mandato coercitivo por el *permiso de descarte*: el modelo queda autorizado a ignorar fragmentos tangenciales e instruido a ejecutar una segunda búsqueda iterativa (*multi-hop*) traduciendo lenguaje coloquial a figuras jurídicas de fondo.
- **Mitigación de Inercia Conversacional y Protocolo Coordinado de Grounding en Códigos Extensos (`gateway/core/alignment_engine.py`, `tools/openwebui_rag_tool.py`, `MANUAL_OPENWEBUI.md`):**
  - Blindaje de turnos de seguimiento y transiciones normativas (*"ahora el vigente"*, *"cómo es hoy?*): prohibición terminante de responder de memoria paramétrica o alucinar números de artículos por inercia de chat.
  - Formalización de la tríada coordinada en embudo para instituciones de derecho positivo en códigos monumentales (ej: CCCN):
    1. Orientación temática y obtención de `doc_id` mediante `buscar_en_base_de_conocimiento`.
    2. Navegación topológica mediante `obtener_estructura_documento` (con filtro) para ubicar el capítulo rector (evitando confusiones inter-ramas como Derecho de Familia vs Contratos).
    3. Extracción de articulado literal e íntegro mediante `leer_documento_completo` (asegurando términos esenciales como *"patrimoniales"* y efectos rectores como *"efecto vinculante"*).
- **Ampliación Universal del Grounding Documental y Refuerzo Anti-Decay en Turnos Avanzados (`gateway/core/alignment_engine.py`, `tools/openwebui_rag_tool.py`, `MANUAL_OPENWEBUI.md`):**
  - Extensión del deber de grounding no solo a derecho positivo y constitucional, sino también a **procedimientos operativos (SOPs), contratos, políticas corporativas y documentación interna de Teccam**.
  - Taxonomía exhaustiva de disparadores de grounding (`GROUNDING_TRIGGERS_PATTERN`) en 6 grupos semánticos: (1) normas, leyes y códigos; (2) procedimientos, plazos y trámites; (3) contratos, cláusulas y penalidades; (4) políticas, seguridad y compliance; (5) instituciones, órganos, atribuciones y potestades (incluyendo Defensor del Pueblo, juzgados, ministerios); (6) manuales y documentación de Teccam.
  - Mecanismo anti-atenuación atencional (*anti-decay*): inyección dinámica en el Gateway de un recordatorio perentorio de grounding al final de la última consulta del usuario ante cualquier término de la taxonomía, neutralizando el *lost-in-the-middle* en sesiones de más de 20 turnos (>50.000 tokens).
  - Sincronización en MongoDB `db.alignment_settings`, `static/js/dashboard_alignment.js` y en la suite de herramientas Open-WebUI.

## [2.7.0] - 2026-09-05

### Added
- **Fail2ban Dinámico Configurable por Entorno (`gateway/core/fail2ban.py`):**
  - Parametrización mediante `FAIL2BAN_MAX_FAILURES` (default 3), `FAIL2BAN_WINDOW_SECONDS` (default 300s) y `FAIL2BAN_BAN_HOURS` (default 48h), con fallbacks automáticos de seguridad.
- **Mitigación de DoS Defensivo & Silent Drop para Lista Negra (`gateway/core/ip_rules.py` y `gateway/proxy/proxy_factory.py`):**
  - Mecanismo en dos fases gobernado por `BLACKLIST_MAX_NOTICES`: emite aviso formal 403 y registro en MongoDB para los primeros intentos; a partir de ahí descarta en seco con cuerpo vacío `b""`, cabecera `Connection: close` y **cero interacción con base de datos o CPU**.
  - Auto-limpieza en memoria: purga periódica en `sync_ip_rules_loop` de IPs cuyos baneos expiran en MongoDB.
- **Protección Anti Self-DoS para Loopback (`FAIL2BAN_EXCLUDE_LOOPBACK`):**
  - Exención configurable para direcciones loopback (`127.0.0.0/8`, `::1`), evitando que pruebas o desajustes locales bloqueen otros microservicios del servidor.
- **Monitoreo Coexistente de Imágenes y Visión en Dashboard (`app_dashboard.py`, `tab_monitor.html`, `sidebar.html`):**
  - Soporte paralelo en "Monitor e Hilos" para **Generador de Imágenes GPU (CUDA)** (`vllm-image`), **Generador de Imágenes CPU (RAM)** (`vllm-sd`) y **Visión Llama (Qwen2.5-VL)** (`vllm-vision`).
  - Puerto `:18200` incorporado en el listado de puertos de la barra lateral.

### Security
- **6to Invariante Operativo MEA (Protección de Secretos y URLs Públicas):**
  - Prohibición formal de hardcodear claves, tokens, URLs públicas y rutas absolutas en código y documentación `*.md`. Sanitización completa de 16 archivos.
- **Zero Trust Gateway y Aislamiento de Clave Maestra:**
  - Desacoplamiento de Planos: la `MASTER_KEY` queda reservada exclusivamente al Plano de Control interno; los puertos del Gateway la rechazan con `HTTP 403` y penalización acumulativa en Fail2ban.

## [2.6.0] - 2026-09-05

### Added
- **Microservicio de Visión Agéntica Desacoplada en RAM (`llama-vision-srv.sh` y `vllm-vision.service`):**
  - Despliegue independiente de Qwen2.5-VL-3B-Instruct (`Q4_K_M` + `mmproj-Q8_0`) en `llama.cpp` (:18200) corriendo 100% en la memoria RAM del sistema con 0 bytes de VRAM (`CUDA_VISIBLE_DEVICES=""`).
- **Puente Multimodal Transparente y Endpoints en Gateway (`gateway/tools/vision.py` y `gateway/proxy/proxy_factory.py`):**
  - Intercepción transparente en `POST /v1/chat/completions` que convierte bloques `image_url` en transcripciones OCR estructuradas en milisegundos, resolviendo el error `image input is not supported` en modelos de texto puro como Gemma 4.
  - Soporte para rutas `POST /api/tools/vision` y `POST /v1/tools/vision` con URLs, Base64 y subidas multipart.
  - Auto-upscaling inteligente con interpolación Lanczos para preservar parches ViT en capturas de baja resolución (evita pérdida de OCR en recortes de remitos).
  - Caché LRU en memoria con huella criptográfica SHA-256 para resolución en 0.0001s en hilos conversacionales continuos.
- **Microservicio de Difusión en CPU/RAM (`sd-image-srv.sh` y `vllm-sd.service`):**
  - Despliegue de SDXL-Turbo 1.0 GGUF (`sd_xl_turbo_1.0.q8_0.gguf`, 3.9 GB) ejecutándose en CPU pura mediante `stable-diffusion.cpp` (`sd-server`) en el puerto `:18004` con 0 MB de VRAM consumida.
  - Inferencia fotorrealista de 512x512 en 1 solo paso (ADD distilled) en 7 a 10 segundos.
- **Submódulo Gateway de Imágenes y Protección de Ventana de Contexto (`gateway/tools/image_gen.py`):**
  - Intercepción de `POST /v1/images/generations` y persistencia automática en disco (`outputs/images/`).
  - Resolución de URLs públicas HTTPS (`https://tu-dominio.com:19000/outputs/images/...`).
  - Purga de payloads Base64 crudos, reduciendo el consumo de tokens en el historial conversacional de **470.974 tokens a solo ~25 tokens**, erradicando el colapso de la ventana de contexto de 131k de Gemma 4.
  - Registro de telemetría de uso en MongoDB (`image`).
- **Herramientas para Open-WebUI y Renderizado Visual Inline:**
  - [`tools/openwebui_vision_tool.py`](tools/openwebui_vision_tool.py): Tool `analizar_o_leer_imagen` para inspección agéntica.
  - [`tools/openwebui_image_tool.py`](tools/openwebui_image_tool.py): Tool `generar_imagen` con directiva estricta al modelo para incrustar Markdown `![prompt](url)`, logrando que Open-WebUI dibuje la imagen automáticamente en pantalla dentro del chat.
- **Documento Arquitectónico Canónico (`docs/ARQUITECTURA_MULTIMODAL_DESACOPLADA_RAM_CPU.md`):**
  - Registro exhaustivo de balance de hardware (RTX 3090 vs RAM DDR4), diagramas de flujo, análisis de fallos y resolución por causa raíz según las Leyes de Ingeniería y el MEA v2.1.

## [2.5.1] - 2026-09-05

### Added
- **Perfil de Producción Canónico para Oficina con RAG Intensivo (`docs/PERFIL_PRODUCCION_GEMMA4_12B_RAG_OFICINA.md`):**
  - Consagrado el estándar dorado para hardware RTX 3090 (24 GB VRAM) + 64 GB RAM utilizando Gemma 4 12B IT Denso bajo `llama.cpp` (`131k ctx`, `batch 4096`, `ubatch 1024`, `mlock`, `reasoning off`). Rinde 2.300-2.450 t/s de prefill y ~63 t/s de generación con 17.7 GB de VRAM estables.
- **Normalización de OCR Soldado en Ingesta (`app_rag_sync.py`):**
  - Desarticulación léxica de números de artículos pegados a la primera palabra (`Artículo 14Todos` $\rightarrow$ `Artículo 14 Todos`).
- **Soporte de Sufijos Normativos en Parser Jerárquico (`app_rag_sync.py` y `rag_engine.py`):**
  - Detección precisa de sufijos legales (`bis`, `ter`, `quater`, etc.) en encabezados y boosting discriminado en LanceDB para evitar solapamientos indebidos.
- **Blindaje Anti-Simulación en 5to Invariante MEA (`gateway/core/alignment_engine.py`):**
  - Prohibición estricta de simulación en texto (`[En proceso de recuperación...]`) y obligatoriedad de tool-call en cualquier solicitud de normas.

### Fixed
- Error de omisión y desplazamiento de artículos en la Constitución Nacional donde el Artículo 14 quedaba absorbido en el Artículo 9 por falta de límite de palabra (`\b`). Reindexado a 168 fragmentos limpios.

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
