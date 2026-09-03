# 🧪 Prueba de Campo: Re-chunking Jerárquico en LanceDB, GPS Anti-Desbordamiento y Búsqueda Quirúrgica RAG

**Fecha:** 2026-09-03 (Sesión Tarde)  
**Entorno:** Ubuntu Linux (RTX 3090 24GB + i9-14900K 64GB)  
**Motor LLM:** `llama-server` (`llama.cpp` clon local compilado) con Qwen 3.6 35B MoE (`Qwen3.6-35B-A3B-Q4_K_M`)  
**Motor Embeddings:** Qwen3-Embedding en puerto `:18005`  
**Base Vectorial:** LanceDB (`teccam_knowledge_base`)  
**Cliente:** Open-WebUI (Docker)  
**Autor:** José Luis Villaronga  
**Agente Operativo:** Antigravity (Google DeepMind)  

---

## 1. Contexto y Diagnóstico Forense de la Causa Raíz

### 1.1. Disparidad Estructural Detectada en LanceDB
En la auditoría de los 35 documentos indexados en LanceDB (10.040 fragmentos iniciales), se detectó una disparidad extrema en la granularidad:
* **Estándar de Oro (Correcto):**  
  * *Ley N° 20.744 de Contrato de Trabajo:* 148 chunks, 63 secciones mapeadas.
  * *Código Procesal Civil y Comercial:* 955 chunks, 702 secciones mapeadas.
* **Colapso por Hiper-Chunking (Anómalo):**  
  * *Código Civil y Comercial de la Nación (CCCN):* 425.630 tokens acumulados en solo **2 chunks**, asignados a **1 única sección ("Sección General")**, conteniendo un chunk monstruoso de **425.453 tokens**.
  * *El Príncipe (Maquiavelo):* 187 chunks acumulados en **1 sola sección**, ignorando sus 26 capítulos.
  * *DNU 70/2023:* 269 chunks en solo 2 secciones.

### 1.2. Causas Raíz Estructurales Identificadas
1. **Causa Raíz A (Pseudo-Tablas Masivas de OCR):**  
   El texto extraído de Teccam PDF para el CCCN venía estructurado en una pseudo-tabla Markdown de 11 líneas donde la línea 8 contenía **2.306.460 caracteres** envueltos en pipes `| ... |`. El algoritmo previo asumía que toda tabla es atómica e indivisible, encapsulando todo el código en un único fragmento continuo.
2. **Causa Raíz B (Miopía de Encabezados):**  
   Obras como *El Príncipe* o decretos utilizaban negritas `**Capitulo I**` o texto legal directo `Título I - ...` sin el prefijo `# ` de Markdown, pasando desapercibidos por el parser jerárquico.
3. **Causa Raíz C (Desbordamiento de Contexto en el GPS Documental):**  
   Al resolver las Causas A y B, el CCCN generó 3.042 secciones individuales. Al solicitar el mapa estructural, `obtener_estructura_documento` generó un volcado Markdown de **667.445 caracteres (~160.000 tokens)**. Esto colapsó la ventana de contexto de `llama-server` (131.072 tokens), abortando con `request (293135 tokens) exceeds the available context size`.
4. **Causa Raíz D (Filtro Estricto de Temas):**  
   La herramienta en Open-WebUI enviaba `dominios="Derecho"`, mientras que LanceDB tenía `"Derecho Argentino"`. La igualdad estricta `doc_topic = 'Derecho'` devolvía 0 resultados inmediatos.

---

## 2. Modificaciones de Ingeniería Implementadas

### A. Aceleración de Ingesta (Prefill) con `--ubatch-size 1024` [Commit `d78a01d`]
* Se integró `LLAMA_UBATCH_SIZE=1024` en `.env`, `llama-srv.sh`, `templates/tabs/tab_config.html` y `static/js/dashboard_core.js`.
* Impacto medido en RTX 3090: aumento de VRAM de 18.6 GB a **19.17 GB** (solo ~570 MB de overhead temporal), dejando **~5 GB de VRAM libres** y acelerando sustancialmente el prefill de ingesta.

### B. Motor de Chunking y Desempaquetado de Tablas [Commit `f859572`]
* **`unpack_pseudo_tables(text)`:** Identifica pseudo-tablas de OCR superiores a 1.500 caracteres con marcadores normativos y las desarticula, restituyendo saltos de línea limpios.
* **`detect_heuristic_header(line)`:** Detección jerárquica multinivel (1: Libro/Parte, 2: Título, 3: Capítulo/Sección, 4: Artículo normativo) y títulos aislados en negrita.
* **Bounded Chunks:** Subdivisión segura por oraciones para que ningún fragmento supere `max_chars` (1.100 caracteres ~ 220 tokens).
* **Purga Determinista:** Inclusión de `table.delete(f"doc_id = '{doc_id}'")` antes de `table.add(...)` para evitar duplicación de registros al re-sincronizar.

### C. Protección Anti-Desbordamiento en GPS Documental [Commit `3d19042`]
* **Límite de Seguridad:** Se estableció `MAX_GPS_ROWS = 50` en `get_document_structure`. El tamaño de la respuesta pasó de 667 KB a **11.9 KB (~2.400 tokens, -98.3% de impacto)**.
* **Parámetro `filtro` Opcional:** Permite al LLM acotar la búsqueda estructural (ej: `obtener_estructura_documento(doc_id="...", filtro="contrato")`).
* **Afinación de Docstrings:** Se instruyó a Open-WebUI a priorizar `buscar_en_base_de_conocimiento` para consultas puntuales.

### D. Búsqueda Flexible por Tema (`LIKE`) [Commit `e0ecbd8`]
* En `rag_engine.py`, la cláusula de tema se modificó de `doc_topic = '...'` a `doc_topic LIKE '%...'`, resolviendo la coincidencia de `"Derecho"` con `"Derecho Argentino"`.

---

## 3. Resultados Cuantitativos Comparativos en LanceDB

| Métrica / Obra | Antes | Después | Impacto Técnico |
| :--- | :---: | :---: | :---: |
| **Código Civil y Comercial (CCCN)** | 2 chunks (1 de 425k tok) | **3.300 chunks** | Fragmentos atómicos de ~120 tokens |
| **Secciones CCCN** | 1 sección | **3.042 secciones** | Árbol completo de artículos normativos |
| **El Príncipe (Maquiavelo)** | 187 chunks, 1 sección | **194 chunks, 27 secciones** | Prólogo + 26 Capítulos indexados |
| **DNU 70/2023** | 269 chunks, 2 secciones | **500 chunks, 419 secciones** | Todos los títulos y artículos identificados |
| **Ley N° 20.744 (Control Regresión)** | 148 chunks, 63 secciones | **148 chunks, 63 secciones** | 🟢 **100% Intacto (Cero regresión)** |
| **Peso Respuesta GPS CCCN** | 667 KB (~160k tokens) | **11.9 KB (~2.4k tokens)** | 🟢 **98.3% de reducción, cero desbordes** |

---

## 4. Evidencia Empírica de Validación en Open-WebUI

### 4.1. Consulta Real del Usuario
> *"Busca en la documentacion definicion de contrato"*

### 4.2. Traza Agéntica del Modelo (Qwen 3.6 MoE)
1. **Llamada 1:** `obtener_indice_biblioteca(solo_vigentes=True, dominio="Derecho")`  
   *Retornó:* Catálogo de 21 obras vigentes, identificando el CCCN (`6a976eb89e1c2342dd2e5b34`).
2. **Llamada 2:** `obtener_estructura_documento(doc_id="6a976eb89e1c2342dd2e5b34", filtro="contrato")`  
   *Retornó:* Mapa acotado de 50 secciones relevantes en 12 KB sin desbordar el contexto.
3. **Navegación Quirúrgica con `leer_documento_completo`:**  
   El modelo leyó de forma focalizada los artículos del Capítulo 1 de Disposiciones Generales:
   * Art. 963 (Prelación) ➔ Art. 962 (Supletoriedad) ➔ Art. 961 (Buena fe) ➔ Art. 960 (Jueces) ➔ Art. 959 (Efecto vinculante) ➔ Art. 958 (Libertad) ➔ **Art. 957 (Definición)**.
4. **Respuesta Generada al Usuario:**
   * **Cita Textual Literal (Art. 957 CCCN):**  
     > *"Contrato es el acto jurídico mediante el cual dos o más partes manifiestan su consentimiento para crear, regular, modificar, transferir o extinguir relaciones jurídicas patrimoniales."*
   * **Análisis Dogmático:** Desglose de acto jurídico, pluralidad, consentimiento, contenido patrimonial y espectro de efectos, con citas del contexto normativo (Art. 958 al 963).
   * **Dictamen:** 100% canónico, fiel al derecho argentino vigente y sin alucinación.

---

## 5. Conclusiones y Cumplimiento de Invariantes MEA v2.1
* **Invariante de Veracidad e Integridad (Gate 1):** Cero simulación; cada fragmento fue extraído directamente de LanceDB.
* **Ley 1 (Modularización):** Componentes aislados entre sincronizador (`app_rag_sync.py`), motor vectorial (`rag_engine.py`), gateway (`rag_endpoints.py`) y cliente (`openwebui_rag_tool.py`).
* **Ley 2 (Causas Raíz):** Se atacó el empaquetado defectuoso de tablas OCR y la rigidez de los filtros SQL en lugar de usar parches temporales.
* **Ley 3 (Mínimo Cambio / Mínimo Blast Radius):** 21/21 pruebas unitarias del Gateway pasando en 1.79s. Cero regresión en obras existentes.
