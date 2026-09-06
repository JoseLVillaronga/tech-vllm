# 📊 Registro de Retrospectivas de Sesión y Métricas MEA

**Proyecto:** vLLM Local Suite / Tech Support Argentina  
**Autor y Supervisor:** José Luis Villaronga  
**Agente Operativo:** Antigravity (Google DeepMind)  
**Marco de Referencia:** [Modelo Ético Adaptativo (MEA v2.1 con Invariantes)](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo) y [Las Tres Leyes Universales](../AGENTS.md)

---

## 🎯 Protocolo Estándar de Cierre de Sesión

Al finalizar cada sesión de trabajo, el agente y el usuario realizan una auditoría automática registrando:

### 1. Métricas Cuantitativas Verificables
* **Turnos de Usuario (`USER_INPUT`):** Cantidad total de peticiones e interacciones enviadas por el usuario.
* **Llamadas Agénticas (`Tool Calls`):** Cantidad total de herramientas ejecutadas (comandos, lecturas, ediciones, búsquedas).
* **Commits en Git:** Total de confirmaciones atómicas realizadas en el repositorio durante la sesión.
* **Invariantes Violados (Gate 1):** Debe ser siempre **0** (binario: veracidad, no-destructividad, anti-parches, objeción).

### 2. Métricas de Integridad y Riesgo (MEA v2.1)
* **RVI Máximo (1-10):** Nivel pico de *Riesgo de Violación de Invariantes* alcanzado durante las tareas más críticas.
* **Blast Radius (Bajo / Medio / Alto):** Radio de impacto y grado de contención de las modificaciones aplicadas.
* **Resolución Causa Raíz:** Evaluación de si los problemas se solucionaron a nivel estructural (Ley 2) o con parches.

---

## 📈 Historial Consolidado de Sesiones

| Fecha | ID Sesión | Turnos Usuario | Llamadas Agénticas (Tools) | Commits Git | Invariantes Violados | RVI Máx | Blast Radius | Estado Global |
| **2026-09-06 (Mediodía - Universalidad de Visión, Reescalado Adaptativo 2D & Prompt Estructurado en 2 Fases)** | `ca5c7e22` | 6 | ~35 | 3 | **0** | 1/10 | Mínimo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-09-05 (Noche - Blindaje Perimetral Zero Trust, Fail2ban Dinámico, Silent Drop y Monitor Multimodal)** | `ca5c7e22` | 15 | ~65 | 7 | **0** | 1/10 | Mínimo (Modular) | 🟢 **100% Exitoso** |
| **2026-09-05 (Tarde - Visión y Difusión en RAM/CPU, Bridge Multimodal & Protección de Contexto)** | `bba5ef3a` | 12 | ~60 | 4 | **0** | 1/10 | Mínimo (Modular) | 🟢 **100% Exitoso** |
| **2026-09-05 (Mañana - Estándar Dorado Gemma 4 12B en RTX 3090, Fix Parser OCR y Blindaje 5to Invariante)** | `bba5ef3a` | 6 | ~35 | 2 | **0** | 1/10 | Mínimo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-09-04 (Noche - Calibración Gemma 4 12B, Boost Canónico RAG, Presets & 5to Invariante MEA)** | `bba5ef3a` | 14 | ~75 | 5 | **0** | 1/10 | Mínimo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-09-03 (Tarde - Re-chunking LanceDB, GPS Anti-Overflow & Búsqueda RAG)** | `bba5ef3a` | 8 | ~50 | 4 | **0** | 2/10 | Mínimo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-09-03 (Mañana - Motor Llama.cpp MoE, Exclusión Mutua & Control GUI)** | `bba5ef3a` | 4 | ~45 | 1 | **0** | 1/10 | Mínimo (Modular) | 🟢 **100% Exitoso** |
| **2026-09-02 (Noche - Freno de Mano RAG & Secuencia Embudo)** | `bba5ef3a` | 6 | ~30 | 2 | **0** | 1/10 | Mínimo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-09-02 (Tarde - Metadata RAG, Mapa Ontológico & Antisesgo)** | `bba5ef3a` | 10 | ~45 | 1 | **0** | 2/10 | Bajo (Modular) | 🟢 **100% Exitoso** |
| **2026-09-02 (Madrugada - Fix Permisos LanceDB)** | `bba5ef3a` | 3 | ~15 | 1 | **0** | 1/10 | Mínimo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-09-01 (Noche - Prefix Caching)** | `bba5ef3a` | 4 | ~12 | 2 | **0** | 1/10 | Mínimo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-09-01 (Mediodía/Tarde)** | `bba5ef3a` | 10 | ~55 | 6 | **0** | 2/10 | Bajo (Modular) | 🟢 **100% Exitoso** |
| **2026-09-01 (Madrugada)** | `bba5ef3a` | 12 | ~40 | 1 | **0** | 2/10 | Bajo (Modular) | 🟢 **100% Exitoso** |
| **2026-08-31 (Noche)** | `b034eae5` | 14 | ~35 | 3 | **0** | 2/10 | Bajo (Quirúrgico) | 🟢 **100% Exitoso** |
| **2026-08-31 (Tarde)** | `18593369` | 9 | ~25 | 1 | **0** | 2/10 | Bajo (Cirugía) | 🟢 **100% Exitoso** |
| **2026-08-30** | `b034eae5` | 192 | 970 | 23 | **0** | 3/10 | Bajo (Modular) | 🟢 **100% Exitoso** |

---

## 📝 Fichas Detalladas por Sesión

### 🔹 Sesión: 2026-09-06 Mediodía/Tarde (`ca5c7e22-5f02-4c3e-8b9d-87b5c9479cce`) - Universalidad de Visión, Reescalado Adaptativo 2D & Blindaje Anti-Sesgo RAG
* **Hitos Principales:**
  1. **Auditoría de Aislamiento de Visión en Modelos Externos:**
     - Verificación rigurosa en código y configuración: se constató que los modelos de proveedores externos (OpenAI, Anthropic, Gemini, DeepSeek Cloud) configurados en Open-WebUI operan por canales directos a sus respectivas APIs, sin pasar por Qwen2.5-VL en RAM ni por el Gateway local, preservando intacta su visión multimodal nativa.
  2. **Universalidad Multi-Modelo y Ahorro Masivo de Contexto ([`docs/ARQUITECTURA_MULTIMODAL_DESACOPLADA_RAM_CPU.md`](../docs/ARQUITECTURA_MULTIMODAL_DESACOPLADA_RAM_CPU.md), [`MANUAL_OPENWEBUI.md`](../MANUAL_OPENWEBUI.md) - Commit `b2c61e5`):**
     - Formalización del principio de universalidad: cualquier LLM local de texto puro (Gemma 4 12B IT, Qwen 2.5 32B/35B, GLM-4.7-Flash 30B MoE, Qwen Coder) queda dotado de visión de alta fidelidad sin requerir proyector `mmproj` ni consumir memoria gráfica en la GPU.
     - Destilación semántica de imágenes a texto estructurado en Markdown (`<contenido_visual_extraido>`), logrando un **ahorro del 85% al 95% en la ventana de contexto** de la GPU respecto a proyectores visuales nativos o Base64.
  3. **Diagnóstico Forense de Causa Raíz en OCR de Documentos Difíciles (Ley 2):**
     - Ante el fallo de transcripción de un remito de baja resolución (`107x193 px`), se analizó la traza completa de logs de `vllm-gateway.service` y `llama-server`. Se constató que el reescalado Lanczos sí operaba (`511x923 px`), pero el prompt interno en español (*"Si hay gráficos, diagramas o fotos..."*) disparaba el filtro de negativa conversacional de Qwen2.5-VL (*"No puedo ver o analizar imágenes..."*), el cual quedaba persistido en la caché en memoria por SHA-256.
  4. **Reescalado Adaptativo 2D por Dimensión y Área Mínima ([`gateway/tools/vision.py`](../gateway/tools/vision.py) - Commit `23c3876`):**
     - Implementación de doble criterio de disparo: $\min(w, h) < 512 \lor w \cdot h < 262.144 \text{ px}^2$.
     - Garantiza que ni recortes mínimos ni imágenes panorámicas de baja resolución queden sub-tokenizadas en el Vision Transformer.
     - Corrección de truncamiento en punto flotante usando `round` para asegurar cumplimiento exacto de la cota mínima de resolución.
  5. **Prompt Estructurado de Visión en 2 Fases (Datos OCR + Descripción Visual):**
     - Separación explícita e imperativa en dos tareas en un solo pase de inferencia:
       1. *Transcripción y Datos* (OCR exhaustivo de textos, números y tablas).
       2. *Descripción Visual* (análisis de componentes, diagramas, figuras y colores).
     - Eliminación total de falsos rechazos en Qwen2.5-VL en español, resolviendo en ~4.5s en CPU con extracción exacta de números (`66252`, `66250`, `66248`) y disposición de filas/columnas.
  6. **Suite de Pruebas Automatizadas y Validación Empírica en UI:**
     - Incorporado test unitario `test_optimize_image_resolution_for_vit` en `tests/test_gateway_tools.py` (29/29 tests aprobados, 100% OK).
     - Validación empírica confirmada directamente por el usuario en Open-WebUI con captura exitosa.
  7. **Blindaje Anti-Sesgo de Anclaje RAG y Permiso de Descarte ([`gateway/core/alignment_engine.py`](../gateway/core/alignment_engine.py), [`tools/openwebui_rag_tool.py`](../tools/openwebui_rag_tool.py) - Commit `aeab647`):**
     - Diagnóstico de sesgo de anclaje: modelos de escala 12B interpretan la directiva clásica (*"responde fundamentando con estos fragmentos"*) como una orden coercitiva de incorporar fragmentos aunque sean tangenciales (ej: derecho de superficie frente a usurpación de tierras).
     - Incorporado el **Principio 6** en las Directivas Fundamentales MEA: evaluación crítica de pertinencia causal directa y prohibición de forzamiento en conclusiones o tablas.
     - Reemplazo por el **permiso de descarte**: autorización explícita para ignorar fragmentos inaplicables e instrucción de ejecutar de inmediato una **segunda búsqueda iterativa (multi-hop)** traduciendo términos coloquiales a figuras típicas de fondo.
     - Sincronización en caliente en MongoDB (`db.alignment_settings`) y en la plantilla del manual de Open-WebUI.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Cero secretos expuestos, cero rutas absolutas, veracidad empírica comprobada en vivo contra `llama-server` y `open-webui`.
  * **Ley 1 (Modularización Estricta):** Cumplida al 100%. Lógica de pre-procesamiento concentrada en `gateway/tools/vision.py` y alineamiento en `gateway/core/alignment_engine.py`.
  * **Ley 2 (Atacar Causas Raíz):** Cumplida al 100%. Se resolvieron tanto los guardrails de visión como el sesgo de anclaje RAG a nivel de diseño de directivas y scaffolding.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Modificaciones quirúrgicas manteniendo total compatibilidad retroactiva.
  * **RVI Máximo:** `1/10`.
  * **Suite de Pruebas:** 29 tests unitarios y end-to-end aprobados (100% OK).

---

### 🔹 Sesión: 2026-09-05 Noche (`ca5c7e22-5f02-4c3e-8b9d-87b5c9479cce`) - Blindaje Perimetral Zero Trust, Fail2ban Dinámico, Silent Drop y Monitor Multimodal
* **Hitos Principales:**
  1. **6to Invariante Operativo MEA y Sanitización Completa ([`AGENTS.md`](../AGENTS.md), [`GEMINI.md`](../GEMINI.md) - Commit `e5f766d`):**
     - Formalización del *Invariante de Seguridad y Protección de Secretos (Anti-Hardcoded Credentials & Sensitive URLs)*: prohibición estricta de hardcodear claves, tokens, URLs de infraestructura pública o rutas absolutas locales en código o documentación `*.md`.
     - Auditoría y saneamiento integral de 16 archivos del repositorio eliminando tokens activos, rutas `/home/jose` y dominios sensibles.
  2. **Desacoplamiento Estricto de Planos (Control vs. Datos) y Zero Trust Gateway ([`gateway/proxy/proxy_factory.py`](../gateway/proxy/proxy_factory.py), [`gateway/core/auth.py`](../gateway/core/auth.py) - Commit `4fcd4d7`):**
     - La `MASTER_KEY` (`API_KEY` de `.env`) quedó restringida al Plano de Control interno (comunicación Gateway $\leftrightarrow$ microservicios locales).
     - Los puertos públicos del Gateway (`:8000`-`:8020`) rechazan de plano la `MASTER_KEY` con `HTTP 403 Forbidden` (`"Acceso denegado: La Clave Maestra está reservada exclusivamente para comunicaciones internas de microservicios. Utiliza una API Key autorizada generada desde el Dashboard."`), forzando el uso de claves autorizadas de MongoDB (`db.api_keys`).
     - Controlado por la variable de entorno `ALLOW_MASTER_KEY_ON_GATEWAY=false`.
  3. **Fail2ban Dinámico y Parametrizable por Entorno ([`gateway/core/fail2ban.py`](../gateway/core/fail2ban.py) - Commit `627cd1e`):**
     - Reemplazo de umbrales cableados en código por la función `get_fail2ban_config()`:
       - `FAIL2BAN_MAX_FAILURES` (default: `3`): umbral de intentos fallidos.
       - `FAIL2BAN_WINDOW_SECONDS` (default: `300`): ventana temporal de cómputo en segundos.
       - `FAIL2BAN_BAN_HOURS` (default: `48`): tiempo de expiración del bloqueo automático en MongoDB (`db.ip_rules`).
  4. **Mitigación de DoS Defensivo & Silent Drop para IPs en Lista Negra ([`gateway/core/ip_rules.py`](../gateway/core/ip_rules.py), [`gateway/proxy/proxy_factory.py`](../gateway/proxy/proxy_factory.py) - Commit `627cd1e`):**
     - Diagnóstico de la vulnerabilidad de amplificación de DoS: responder repetidamente con `HTTP 403` JSON y despachar hilos a MongoDB en cada petición desde IPs bloqueadas colapsa los recursos del Gateway ante ráfagas de ataque.
     - Implementado contador en memoria y transición de dos fases gobernada por `BLACKLIST_MAX_NOTICES` (default `3`):
       - Primeros 3 intentos: respuesta formal `HTTP 403 Forbidden` y auditoría en `blocked_requests`.
       - Intento 4 en adelante: **Silent Drop instantáneo** devolviendo cuerpo binario vacío `b""`, cabecera `Connection: close` y **cero interacción con MongoDB/CPU**.
     - Auto-purga en memoria: en cada ciclo de sincronización de 10s (`sync_ip_rules_loop`), los contadores de IPs cuyo baneo expiró en MongoDB son liberados automáticamente, evitando fugas de memoria.
  5. **Activación de Fail2ban ante Intentos con Clave Maestra (Commit `0bae968`):**
     - Toda petición externa que intente presentar la Clave Maestra en el Gateway suma fallos a Fail2ban (`await register_failed_attempt(client_ip)`), aplicando auto-ban en MongoDB al acumularse 3 intentos.
  6. **Prevención de Self-DoS y Exclusión de Loopback (Commit `9d5ccd6`):**
     - Observado en pruebas reales que el baneo de `127.0.0.1` bloqueaba las comunicaciones internas de microservicios en localhost (como Whisper).
     - Incorporada la directiva `FAIL2BAN_EXCLUDE_LOOPBACK=true` (opcional por `.env`): exime a `127.0.0.0/8` y `::1` de acumular auto-baneos accidentales sin comprometer el rechazo del acceso con `HTTP 403`.
  7. **Monitorización Multimodal Coexistente en Dashboard ([`app_dashboard.py`](../app_dashboard.py), [`tab_monitor.html`](../templates/tabs/tab_monitor.html) - Commits `2a0af07` y `f6cc023`):**
     - Reorganizado el panel "Monitor e Hilos" para reflejar la dualidad de motores:
       - **Generador de Imágenes GPU (CUDA)** (`vllm-image`): PyTorch/Diffusers en `:18004` (inactivo por perfil RAG intensivo, disponible bajo demanda).
       - **Generador de Imágenes CPU (RAM)** (`vllm-sd`): `stable-diffusion.cpp` en `:18004` (activo con 0 MB de VRAM).
       - **Visión Llama (Qwen2.5-VL)** (`vllm-vision`): `llama-server` en `:18200` (activo con 0 MB de VRAM).
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Cumplimiento riguroso de no-destructividad, veracidad verificada en vivo con `curl`, cero rutas absolutas y protección absoluta de secretos.
  * **Ley 1 (Modularización Estricta):** Cumplida al 100%. Fail2ban, reglas de IP y Dashboard desacoplados en submódulos especializados.
  * **Ley 2 (Atacar Causas Raíz):** Cumplida al 100%. Se atacó la causa raíz del DoS por logging excesivo mediante Silent Drop y el Self-DoS mediante exclusión de loopback.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Intervenciones quirúrgicas en cada submódulo sin alterar el tráfico de producción ni romper contratos de microservicios existentes.
  * **RVI Máximo:** `1/10`.
  * **Suite de Pruebas:** 28 tests unitarios y end-to-end ejecutados y aprobados (100% OK).

---

### 🔹 Sesión: 2026-09-05 Tarde (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Visión y Difusión Desacopladas en RAM/CPU, Bridge Multimodal y Protección de Contexto
* **Hitos Principales:**
  1. **Microservicio de Visión Agéntica en RAM (`vllm-vision.service` en `:18200`):**
     - Despliegue de Qwen2.5-VL-3B-Instruct (`Q4_K_M` + `mmproj-Q8_0`) en `llama-server` corriendo 100% en RAM y 8 hilos de CPU con `CUDA_VISIBLE_DEVICES=""` (**0 MB de VRAM consumida**).
     - Validación empírica: 37.7 t/s en evaluación visual y ~10 t/s en generación OCR, permitiendo a Gemma 4 razonar sobre comprobantes y facturas sin reducir su ventana de 131k tokens.
  2. **Puente Multimodal Transparente en API Gateway ([`gateway/tools/vision.py`](../gateway/tools/vision.py)):**
     - Intercepción de bloques `image_url` en `POST /v1/chat/completions`. Permite al usuario arrastrar imágenes directamente al chat de Open-WebUI sin configurar herramientas.
     - Auto-escalado de resolución con interpolación Lanczos para evitar la pérdida de parches ViT en capturas pequeñas (solucionó el caso de recortes de remitos).
     - Caché LRU en memoria con huellas SHA-256 (resolución en 0.0001s en turnos subsiguientes).
  3. **Microservicio de Difusión en CPU/RAM (`vllm-sd.service` en `:18004`):**
     - Compilación nativa C++ de `stable-diffusion.cpp` (`sd-server`) con optimizaciones AVX2 y OpenMP.
     - Pesos GGUF `sd_xl_turbo_1.0.q8_0.gguf` (3.9 GB) ejecutándose en **1 solo paso** (ADD Distilled) con **0 MB de VRAM**. Inferencia de 512x512 en 7-10 segundos en CPU.
  4. **Protección de la Ventana de Contexto (Persistencia en Disco vs. Base64) ([`gateway/tools/image_gen.py`](../gateway/tools/image_gen.py)):**
     - Diagnóstico de la falla `request (470974 tokens) exceeds available context size (131072 tokens)` originada por el Base64 crudo de 512x512 (~670.000 caracteres) inyectado en el turno del asistente.
     - Solución estructural: El Gateway intercepta `/v1/images/generations`, guarda el PNG en `outputs/images/` y devuelve una URL HTTPS pública (`https://tu-dominio.com:19000/outputs/images/...`).
     - **Reducción de tokens: de 470.974 tokens a solo ~25 tokens**, erradicando el colapso del contexto.
  5. **Renderizado Visual Inline en Open-WebUI ([`tools/openwebui_image_tool.py`](../tools/openwebui_image_tool.py)):**
     - Identificado que la caja de depuración de Open-WebUI (`View Result from...`) no procesa HTML/Markdown por diseño de seguridad.
     - Contrato de la herramienta actualizado para instruir imperativamente a Gemma 4 a estampar `![prompt](URL)` en su respuesta final.
     - Validación empírica: Gemma 4 incluye el enlace y la imagen se dibuja automáticamente en alta resolución dentro de la burbuja del chat.
  6. **Documentación Arquitectónica Canónica:**
     - Creación de [`docs/ARQUITECTURA_MULTIMODAL_DESACOPLADA_RAM_CPU.md`](ARQUITECTURA_MULTIMODAL_DESACOPLADA_RAM_CPU.md).
     - Actualización de [`MANUAL_OPENWEBUI.md`](../MANUAL_OPENWEBUI.md) con las Herramientas 5 y 6.
     - Actualización de [`CHANGELOG.md`](../CHANGELOG.md) con la versión 2.6.0.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Veracidad técnica absoluta (pruebas reales ejecutadas en vivo), cero destructividad, portabilidad completa sin rutas absolutas (`Path(__file__)`).
  * **Ley 1 (Modularización Estricta):** Cumplida al 100%. Visión desacoplada en `gateway/tools/vision.py` y difusión en `gateway/tools/image_gen.py`. Servicios independientes en systemd.
  * **Ley 2 (Atacar Causas Raíz):** Cumplida al 100%. Se resolvió la raíz del colapso de 470k tokens persistiendo en disco y sirviendo URLs públicas. Se resolvió la ceguera del ViT en recortes con auto-upscaling Lanczos.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Inferencia de Gemma 4 en GPU y embeddings preservados al 100% sin ninguna interferencia ni alteración de contratos.
  * **RVI Máximo:** `1/10`.

---

### 🔹 Sesión: 2026-09-05 Mañana (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Estándar Dorado Gemma 4 12B en RTX 3090, Fix Parser OCR y Blindaje 5to Invariante
* **Hitos Principales:**
  1. **Diagnóstico Forense de OCR Soldado y Falsos Límites de Palabra (`\b`):**
     - Identificado que en textos legales con OCR (como la Constitución Nacional), artículos como `Artículo 14Todos...` o `Artículo 10En...` rompían la expresión regular de encabezados por falta de límite de palabra (`\b` no existe entre un dígito y una letra).
     - Esto causaba que el Artículo 14 fuera engullido dentro del Artículo 9, y que el Artículo 14 bis fuera erróneamente rotulado como Artículo 14.
  2. **Resolución Estructural en el Chunker ([`app_rag_sync.py`](../app_rag_sync.py) - Commit `7e3388d`):**
     - Normalización léxica previa que desarticula números pegados a palabras (`Artículo 14Todos` $\rightarrow$ `Artículo 14 Todos`).
     - Detección de encabezados Nivel 4 robustecida sin dependencia de `\b`, con soporte formal para sufijos normativos (`bis`, `ter`, `quater`, etc.) y subtítulos.
     - Re-indexación de la Constitución en **168 fragmentos** con secciones independientes y limpias (`Artículo 10`, `Artículo 14`, `Artículo 14 bis`, `Artículo 15`).
  3. **Boosting Léxico Discriminado en LanceDB ([`rag_engine.py`](../rag_engine.py) - Commit `7e3388d`):**
     - Diferenciación estricta entre artículos base y derivados: una búsqueda de `"Artículo 14"` no impulsa erróneamente `"Artículo 14 bis"`, y viceversa.
     - Pruebas directas: Artículos 10, 14, 14 bis, 15 y Preámbulo recuperados en el **Puesto #1 con 119% de score y latencias de 70 a 90 ms**.
  4. **Blindaje Ético Anti-Simulación ([`gateway/core/alignment_engine.py`](../gateway/core/alignment_engine.py) y [`static/js/dashboard_alignment.js`](../static/js/dashboard_alignment.js)):**
     - 5to Invariante extendido a toda solicitud directa de normas (prohibición de responder de memoria).
     - Prohibición expresa de "simulación mental en texto" (`[En proceso de recuperación...]`).
     - Validación en Open-WebUI: **7 de 7 consultas (100%)** ejecutaron llamadas técnicas a herramientas sin alucinación alguna.
  5. **Declaración del Estándar Dorado de Producción ([`PERFIL_PRODUCCION_GEMMA4_12B_RAG_OFICINA.md`](PERFIL_PRODUCCION_GEMMA4_12B_RAG_OFICINA.md)):**
     - Formalizado el documento de referencia de hardware (RTX 3090 24GB + 64GB RAM) que consagra a **Gemma 4 12B IT denso bajo `llama.cpp`** (`131k ctx`, `batch 4096`, `ubatch 1024`, `mlock`, `reasoning off`) como la mejor opción de producción para oficinas con RAG intensivo (~2.300 t/s prefill, ~63 t/s generación, 17.7 GB VRAM estables con 6.3 GB de margen).
* **Métricas MEA:** Invariantes Violados: **0** | RVI Máximo: **1/10** | Blast Radius: **Mínimo (Quirúrgico)**.

---

### 🔹 Sesión: 2026-09-04 Noche (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Calibración Gemma 4 12B, Boost Canónico RAG, Presets & 5to Invariante MEA
* **Hitos Principales:**
  1. **Diagnóstico Forense de Visión en Gemma 4 bajo `llama.cpp`:**
     - Identificado que en `llama.cpp` la visión requiere proyector multimodal (`--mmproj`). Se integró y probó `mmproj-gemma-4-12B-it-f16.gguf` (116 MB).
     - Identificado que la arquitectura de visión unificada `gemma4uv` es experimental upstream en `llama.cpp` (PRs #24077/#24082) y sufre de desalineación en atención no causal, recomendándose su uso para visión en `vLLM` nativo.
     - Calibrado Gemma 4 12B IT para texto puro y RAG de alta velocidad: VRAM estabilizada en 17.7 GB con 131k de contexto, 60 t/s de generación sostenida y 2.300 t/s de prefill en RTX 3090.
  2. **Descontaminación de Citas en Encabezados Jerárquicos ([`app_rag_sync.py`](../app_rag_sync.py)):**
     - Eliminación previa de enlaces `[...](...)` y corchetes doctrinarios antes de evaluar longitud de títulos en `detect_heuristic_header`.
     - Re-indexación de CCCN en 3.291 chunks, recuperando el título padre `TITULO II Contratos en general` en la ruta jerárquica del Artículo 957.
  3. **Re-ranking Canónico para Figuras Rectoras ([`rag_engine.py`](../rag_engine.py)):**
     - Implementado boosting definitorio (+0.06 de similitud) para fragmentos de *Disposiciones Generales*, *Parte General* o *Título Preliminar* ante consultas definitorias (*"definición"*, *"concepto"*, *"qué es"*).
     - Elevado el Artículo 957 (Definición de Contrato) del puesto #10 al **Puesto #1 absoluto (88.41% de coincidencia)**, resolviendo en una sola llamada de 95 ms.
  4. **Implementación del 5to Invariante Operativo MEA ([`gateway/core/alignment_engine.py`](../gateway/core/alignment_engine.py)):**
     - Neutralizado el sesgo de inercia y defensividad complaciente (*sycophancy*) ante repreguntas.
     - Mandato estricto: ante solicitudes de fuentes, artículos o alcance normativo (*"¿esto abarca X?", "especifica la fuente"*), queda terminantemente prohibido responder de memoria; es obligatorio emitir llamada a la herramienta de búsqueda documental.
     - Verificado en campo: Gemma 4 frenó la adivinación y consultó la **Ley General de Sociedades 19.550**, citando con 100% de exactitud los Arts. 56, 57, 147 y la inoponibilidad jurídica.
  5. **Sincronización Canónica en Dashboard GUI ([`static/js/dashboard_alignment.js`](../static/js/dashboard_alignment.js)):**
     - Sincronizada la constante `CANONICAL_INVARIANTS_PROMPT` con los 5 invariantes operativos completos para que el botón *"Restaurar Invariantes Canónicos"* sea 100% resiliente.
  6. **Mapeo de Variables `LLAMA_*` y Botón de Preset Rápido ([`templates/tabs/tab_config.html`](../templates/tabs/tab_config.html) y [`static/js/dashboard_core.js`](../static/js/dashboard_core.js)):**
     - Inventario exhaustivo de 14 variables de entorno documentadas.
     - Botón `⚡ Gemma 4 12B (Denso / VRAM Baja)` en el Dashboard para alternar de inmediato entre Qwen 35B MoE y Gemma 4 12B Denso.
     - Incorporado campo editable `LLAMA_DIR` respetando el 4to Invariante de portabilidad.
  7. **Análisis de Concurrencia de Oficina (5 Personas) y Riesgo de Fragmentación ([`INTEGRACION_LLAMACPP_Y_QWEN_MOE.md`](INTEGRACION_LLAMACPP_Y_QWEN_MOE.md)):**
     - Evaluación técnica de `--parallel 1` (cola FIFO) vs `--parallel N` (slots rígidos).
     - Determinación canónica por Ley 2 (causa raíz / prevención de fallos en cadena): mantener `--parallel 1` para preservar el 100% de los 131k tokens íntegros para cualquier consulta RAG pesada sin riesgo de truncamiento.
  8. **Validación de Sensibilidad Ética:**
     - Verificada respuesta empática, rigurosa y orientadora ante consultas sobre delitos contra la integridad sexual (Código Penal Art. 119), orientando hacia asistencia letrada y psicológica profesional.
* **Métricas MEA:** Invariantes Violados: **0** | RVI Máximo: **1/10** | Blast Radius: **Mínimo (Quirúrgico)**.

---

### 🔹 Sesión: 2026-09-03 Tarde (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Re-chunking Jerárquico en LanceDB, GPS Anti-Desbordamiento y Búsqueda RAG Quirúrgica
* **Hitos Principales:**
  1. **Aceleración de Ingesta (Prefill) con `--ubatch-size 1024` ([Commit `d78a01d`](../llama-srv.sh)):**
     - Configuración de `LLAMA_UBATCH_SIZE=1024` en `.env` y `llama-srv.sh` para acelerar el procesamiento de contexto masivo en RTX 3090.
     - Medición en caliente: VRAM subió de 18.6 GB a 19.17 GB (solo ~570 MB temporales), dejando ~5.0 GB libres y alcanzando 54.7 t/s.
     - Controles reactivos integrados en Dashboard (`tab_config.html` y `dashboard_core.js`).
  2. **Diagnóstico Forense de LanceDB y Causas Raíz Estructurales:**
     - Identificado colapso en CCCN (1 hiper-chunk de 425k tokens en 1 sección) debido a pseudo-tablas continuas de OCR con 2.3M caracteres.
     - Identificada miopía de encabezados en obras sin `# ` como *El Príncipe* (1 sección para 26 capítulos) y *DNU 70/2023*.
  3. **Reestructuración del Chunking Jerárquico ([`app_rag_sync.py`](../app_rag_sync.py) - [Commit `f859572`](../app_rag_sync.py)):**
     - Función `unpack_pseudo_tables`: desarticula pseudo-tablas masivas de OCR (>1.500 chars) restituyendo saltos de línea estructurales.
     - Función `detect_heuristic_header`: detección multinivel de títulos (Libros, Títulos, Capítulos, Artículos y negritas).
     - Subdivisión acotada (*Bounded Chunks*): garantiza que ningún fragmento supere `max_chars` (1.100 caracteres ~ 220 tokens).
     - Purga determinista: asegura la eliminación previa de registros antiguos (`table.delete(doc_id)`) antes de insertar nuevos.
     - Re-indexación CCCN: pasó de 2 chunks y 1 sección a **3.300 chunks y 3.042 secciones**.
     - Re-indexación El Príncipe: pasó de 1 sección a **27 secciones (26 capítulos)**.
     - Re-indexación DNU 70/2023: pasó de 2 secciones a **419 secciones**.
     - Cero regresión en Ley 20.744 (148 chunks, 63 secciones intactas).
  4. **Protección Anti-Desbordamiento en GPS Documental ([`rag_engine.py`](../rag_engine.py) - [Commit `3d19042`](../rag_engine.py)):**
     - Límite de seguridad `MAX_GPS_ROWS = 50` con advertencia de granularidad, reduciendo el payload de 667 KB a 11.9 KB (-98.3% tokens).
     - Soporte para parámetro `filtro` opcional en `get_document_structure(doc_id, filtro=...)` para acotamiento temático.
     - Afinación de docstrings en [`tools/openwebui_rag_tool.py`](../tools/openwebui_rag_tool.py) y endpoints del Gateway.
  5. **Búsqueda Flexible por Tema ([`rag_engine.py`](../rag_engine.py) - [Commit `e0ecbd8`](../rag_engine.py)):**
     - Cláusula `doc_topic LIKE '%...%'` en LanceDB para que consultas con `dominios="Derecho"` coincidan directamente con `"Derecho Argentino"`.
  6. **Validación Empírica en Open-WebUI:**
     - Consulta: *"Busca en la documentacion definicion de contrato"*.
     - El modelo Qwen 3.6 MoE navegó las herramientas, extrajo el **Artículo 957 del CCCN** con precisión literal del 100% y cero alucinaciones dentro del presupuesto de contexto.
* **Métricas MEA:** Invariantes violados: **0** | RVI Máx: **2/10** | Blast Radius: **Mínimo (Quirúrgico)** | Tests Unitarios: **21/21 OK**.

---

### 🔹 Sesión: 2026-09-03 Mañana (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Motor Llama.cpp Qwen 3.6 MoE, Exclusión Mutua Systemd y Control GUI
* **Hitos Principales:**
  1. **Integración de `llama.cpp` (`llama-server`) para Qwen 3.6 35B MoE (A3B Q4_K_M):**
     - Configuración de parámetros óptimos en `.env`: contexto de 128k, batch de 4096, 256 capas GPU, 18 expertos CPU y modo agéntico con `--reasoning off`.
     - Rendimiento empírico sostenido de **~670 tokens/s de prefill** y **~50 tokens/s de generación**.
     - Solución de la advertencia de memoria bloqueada mediante ejecución con `User=root` y `LimitMEMLOCK=infinity` en systemd.
  2. **Lanzador Dinámico y Portable ([`llama-srv.sh`](../llama-srv.sh)):**
     - Cumplimiento estricto del 5to Invariante (Anti-hardcoded paths): resolución dinámica del usuario real (`jose`) y su `$HOME` incluso bajo ejecución como `root`.
     - Reemplazo de proceso mediante `exec` para control nativo de PID por systemd.
  3. **Exclusión Mutua Bidireccional ([`check_service_conflict.sh`](../check_service_conflict.sh)):**
     - Guardia modular que valida que el servicio oponente no esté activo y que el puerto 18100 no esté en uso.
     - Si `vllm-llama` está activo y se intenta iniciar `vllm`, se aborta inmediatamente con código de salida 1 y mensaje en journalctl sin afectar al servicio en ejecución, y viceversa.
  4. **Instalador de Servicio ([`install_llama_service.sh`](../install_llama_service.sh)) y Actualización de `vllm.service`:**
     - Creación de `vllm-llama.service` y actualización de `vllm.service` con pre-check de conflicto.
     - Soporte dual en [`sync_rag_scheduled.sh`](../sync_rag_scheduled.sh) para pausar y restaurar automáticamente el motor LLM activo durante la sincronización RAG nocturna.
  5. **Panel de Monitoreo y Edición de Variables en Dashboard Web:**
     - Incorporación de tarjeta de servicio `Llama.cpp LLM (Qwen MoE)` en [`tab_monitor.html`](../templates/tabs/tab_monitor.html) con controles Start/Stop/Restart.
     - Corrección en [`static/js/dashboard_core.js`](../static/js/dashboard_core.js) para actualización en tiempo real del badge (`ACTIVE`).
     - Nueva sección dedicada en [`tab_config.html`](../templates/tabs/tab_config.html) para visualizar y modificar las 10 variables de `llama.cpp` con botón de configuración óptima rápida y persistencia en `.env`.
  6. **Suite de Pruebas Unitarias:**
     - 21/21 tests ejecutados y pasando al 100% en `tests/test_gateway_core.py` y `tests/test_gateway_tools.py`.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Cero destructividad, transparencia total en pruebas y eliminación de rutas hardcodeadas.
  * **Ley 1 (Modularización):** Cumplida al 100%. La exclusión mutua se aisló en un script independiente reutilizable por ambos servicios.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. El problema de memoria bloqueada se resolvió configurando el servicio systemd con `LimitMEMLOCK=infinity` en lugar de omitir la optimización.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Las mejoras de UI y scripts no alteraron la estabilidad de los demás servicios.
  * **RVI Máximo:** `1/10`.

### 🔹 Sesión: 2026-09-02 Noche (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Freno de Mano RAG, Prevención de Desbordamiento y Embudo Agéntico
* **Hitos Principales:**
  1. **Análisis Forense de Historiales de Chat (`temp_historial_chat/`):**
     - Identificación del origen del error de vLLM `131073 tokens > 131072 tokens` por avidez estocástica en Gemma 4 12B local al intentar volcar la "Sección General" del CCCN (~425.630 tokens), inflando el prompt a 122.881 tokens y el archivo JSON a 2.37 MB.
  2. **Implementación de Freno de Mano en Motor RAG ([`rag_engine.py`](../rag_engine.py)):**
     - Detección y bloqueo automático de solicitudes de lectura completa o secciones masivas en obras > 25.000 tokens sin pasar por el GPS Documental.
     - Límite duro `MAX_SAFE_TOOL_TOKENS = 15.000 tokens` con truncado preventivo seguro para impedir saturación de contexto bajo cualquier circunstancia.
  3. **Protocolo Obligatorio de Secuencia en Embudo ([`gateway/core/alignment_engine.py`](../gateway/core/alignment_engine.py)):**
     - Refuerzo de la Regla 4 del MEA con el protocolo canónico de 3 pasos (Macro: Índice ➔ Medio: GPS ➔ Quirúrgico: Lectura acotada) y sincronización inmediata con MongoDB (`alignment_settings`).
  4. **Actualización de Tool Open-WebUI a v2.2.0 ([`tools/openwebui_rag_tool.py`](../tools/openwebui_rag_tool.py)):**
     - Ajuste de `token_threshold = 15000` y docstring con la *Regla de Oro Obligatoria*.
  5. **Verificación Empírica Inmediata:**
     - Chat ID `0e8daf98-36ff-4733-ba73-5d0f00942f98`: Activación exitosa del freno de mano, reducción del 93.3% en uso de contexto (de 122.8K a **8.175 tokens**), cero saturación y respuesta jurídica con **cero alucinación** sobre el Art. 957 y requisitos de validez del CCyC argentino.
  6. **Documentación Técnica de Prueba de Campo:**
     - Elaboración de [`docs/pruebas_campo/prueba_campo_freno_mano_rag_y_secuencia_embudo_2026-09-02.md`](pruebas_campo/prueba_campo_freno_mano_rag_y_secuencia_embudo_2026-09-02.md).
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**.
  * **Ley 1 (Modularización):** Cumplida al 100%. Lógica de control encapsulada en el motor de RAG y alineación.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Se atacó el origen del desbordamiento en el backend y en la directiva de sampling en lugar de aplicar parches superficiales.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Intervenciones mínimas con 21/21 tests unitarios pasando en verde.
  * **RVI Máximo:** `1/10`.

### 🔹 Sesión: 2026-09-02 Tarde (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Metadata de Vigencia, Mapa Ontológico Global y Protocolo Antisesgo
* **Hitos Principales:**
  1. **Evolución Dinámica de Esquema en LanceDB:** Incorporación de columnas `doc_vigencia` y `doc_fecha_publicacion` con actualización diferencial in-place de los 35 documentos existentes desde la API oficial de Teccam PDF (`:5022`) en 7 segundos sin uso de VRAM ni recómputo de vectores.
  2. **Alertas Proactivas de Recencia y Vigencia:** Marcado explícito de estado `[VIGENTE]` y advertencia de seguridad para normas derogadas (`[DEROGADO]`) o parciales para impedir que el LLM confunda normas históricas con derecho positivo aplicable.
  3. **Mapa Ontológico Global (`get_library_index`):** Implementación del árbol temático jerarquizado en 7 dominios y 35 obras con sugerencias directas de invocación de herramientas (`obtener_estructura_documento` y `leer_documento_completo`).
  4. **Tolerancia Multi-Término en Filtrado Temático:** Manejo resiliente de separadores (`/`, `,`, `-`, `|`, espacios) para búsquedas de dominio (ej: `Filosofia/Etica` ➔ mapeo simultáneo de `Filosofia` y `Filosofia Etica`), resolviendo el bloqueo agéntico observado en modelos compactos de 12B.
  5. **Protocolo Antisesgo de Confirmación (Regla 4 en MEA Alignment):** Refuerzo en el `DEFAULT_INVARIANTS_PROMPT` y MongoDB (`alignment_settings`) con mandato explícito de verificar fuentes con tools antes de emitir afirmaciones normativas de memoria previa y navegar en cadena ante versiones evolutivas (`v1` vs `v2.1`).
  6. **Actualización de Dashboard Web (:8004):** Columnas de Vigencia y Fecha de Publicación con badges semánticos Glassmorphism y modal interactivo para consultar el Mapa Ontológico Global.
  7. **Actualización de Tool Open-WebUI:** Publicación de la v2.1.0 exponiendo las 4 herramientas del embudo progresivo (`obtener_indice_biblioteca`, `buscar_en_base_de_conocimiento`, `obtener_estructura_documento`, `leer_documento_completo`).
  8. **Suite de Pruebas Automatizadas:** 21/21 tests ejecutados y pasando en verde (100% OK) en 1.60 segundos.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Transparencia absoluta, cero destructividad y verificación empírica constante.
  * **Ley 1 (Modularización):** Cumplida al 100%. Lógica distribuida con cohesión en `rag_engine.py`, `app_rag_sync.py`, `gateway/tools/rag_endpoints.py` y `gateway/core/alignment_engine.py`.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Se atacó el origen del sesgo de complacencia en el prompt de alineación y la causa del fallo de filtrado sintáctico con regex tolerante.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Cero downtime, actualización in-place y compatibilidad hacia atrás intacta.
  * **RVI Máximo:** `2/10`.

### 🔹 Sesión: 2026-09-02 Madrugada (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Reparación de Permisos LanceDB & Portabilidad POSIX
* **Hitos Principales:**
  1. **Diagnóstico de Causa Raíz de 'Permission denied (os error 13)':**
     - Identificación del bloqueo en la lectura de LanceDB por parte de servicios ejecutados como usuario regular (`jose`) debido a la creación de fragmentos con permisos `600` / `nobody:nogroup` tras la sincronización nocturna desatendida (`root/systemd`).
  2. **Resolución Estructural y Autocorrección Dinámica POSIX ([`sync_rag_scheduled.sh`](../sync_rag_scheduled.sh) y [`app_rag_sync.py`](../app_rag_sync.py)):**
     - Implementación de determinación dinámica del propietario de la carpeta (`stat -c '%U' "${PROJECT_DIR}"`) y su grupo principal (`id -gn`) sin hardcodeo de nombres ni rutas.
     - Inyección de `umask 0022` y pase garantizado de permisos `u+rwX,g+rwX,o+rX` en la función `cleanup()` del orquestador y al cierre de la ingesta en Python.
  3. **Restablecimiento y Verificación:**
     - Restauración inmediata de la visibilidad de los **35 documentos indexados** y **10.040 fragmentos vectoriales** en el Dashboard Web (:8004) y endpoints de búsqueda del Gateway.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Cumplimiento estricto del **5to Invariante (Portabilidad y Anti-Hardcoded Paths)** mediante introspección POSIX dinámica.
  * **Ley 1 (Modularización):** Cumplida al 100%. Lógica de permisos encapsulada en los hooks de sincronización.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Se atacó el origen del problema de permisos en el proceso de ingesta desatendida.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Corrección quirúrgica de 2 archivos sin alterar APIs ni datos.
  * **RVI Máximo:** `1/10`.

### 🔹 Sesión: 2026-09-01 Noche (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`) - Optimización Prefix Caching
* **Hitos Principales:**
  1. **Habilitación de Prefix Caching en vLLM ([`app.py`](../app.py)):**
     - Integración de `--enable-prefix-caching` gobernada por la variable de entorno `ENABLE_PREFIX_CACHING` (por defecto `True`).
     - Reutilización de bloques de memoria KV Cache para el *System Prompt del MEA*, esquemas de herramientas e historial multi-turno con **cero costo de VRAM adicional** mediante la estructura *Radix Tree* y política de desalojo LRU de vLLM.
  2. **Actualización de Documentación Técnica y Manuales ([`README.md`](../README.md) y [`MANUAL_OPENWEBUI.md`](../MANUAL_OPENWEBUI.md)):**
     - Creación de la **Sección 13** en *Aprendizajes Técnicos y Optimizaciones* de `README.md`.
     - Documentación de la aceleración del *Time-To-First-Token* (TTFT cayendo de ~800 ms a **< 20 ms**) en cadenas de extracción y comparativas multi-sección en `MANUAL_OPENWEBUI.md`.
     - Actualización de `.env.example` con la nueva directiva.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Transparencia absoluta en el análisis de memoria y ejecución determinista.
  * **Ley 1 (Modularización):** Cumplida al 100%. Parámetro limpio desacoplado en configuración.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Se eliminó el *prefill lag* en el núcleo de inferencia sin requerir hacks en el cliente.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Intervención quirúrgica directa sin efectos secundarios en otros modelos.
  * **RVI Máximo:** `1/10`.

### 🔹 Sesión: 2026-09-01 Mediodía/Tarde (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`)
* **Hitos Principales:**
  1. **Motor RAG Jerárquico v2.1 & GPS Documental ([`rag_engine.py`](../rag_engine.py)):**
     - Creación de `get_document_structure(doc_id)`: Escaneo y agrupamiento del árbol de secciones (`section_path`), cálculo de tokens por capítulo/título y generación de un "GPS Documental" en Markdown.
     - Implementación de `_partition_chunks_dynamically`: Particionado inteligente con tolerancia dinámica ($\pm 5\% - 8\%$) para alinear cortes de paginación a límites naturales de capítulos/artículos en lugar de cortes ciegos de tokens.
     - Extracción focalizada por sección: Parámetro `seccion` en `get_document_full_content(doc_id, seccion="...")` para consultas directas y quirúrgicas de capítulos o libros específicos (~50 ms de latencia).
     - Nuevos endpoints `POST /api/tools/rag-structure` y `POST /v1/rag/structure` en [`gateway/tools/rag_endpoints.py`](../gateway/tools/rag_endpoints.py) y [`gateway/proxy/proxy_factory.py`](../gateway/proxy/proxy_factory.py).
     - Actualización de [`tools/openwebui_rag_tool.py`](../tools/openwebui_rag_tool.py) a v2.0.0 con `obtener_estructura_documento` y soporte de `seccion`.
     - Botón "GPS" y modal interactivo *Glassmorphism* en la pestaña Base RAG del Dashboard Web ([`templates/tabs/tab_rag.html`](../templates/tabs/tab_rag.html) y [`static/js/dashboard_rag.js`](../static/js/dashboard_rag.js)).
  2. **Catálogo de Pruebas de Campo Empíricas ([`docs/pruebas_campo/`](pruebas_campo/README.md)):**
     - 🧪 [`prueba_campo_62k_matrimonio_pdf_2026-09-01.md`](pruebas_campo/prueba_campo_62k_matrimonio_pdf_2026-09-01.md): Digestión masiva de 59.3K tokens en `Gemma 4 12B-it` (62.012 tokens acumulados) y generación del PDF `Informe_Nulidad_Matrimonio_Teccam.pdf` (2 páginas).
     - 🧪 [`prueba_campo_rag_jerarquico_v2_2026-09-01.md`](pruebas_campo/prueba_campo_rag_jerarquico_v2_2026-09-01.md): Validación del ciclo de 3 pasos (Búsqueda ➔ GPS de 196 secciones ➔ Extracción quirúrgica de 5.7K tokens).
     - 🧪 [`prueba_campo_deepseek_v4_evaluacion_rag_2026-09-01.md`](pruebas_campo/prueba_campo_deepseek_v4_evaluacion_rag_2026-09-01.md): Evaluación crítica por DeepSeek-V4, diagnóstico de vigencia temporal y generación de la Guía Oficial de 24 leyes en PDF de 4 páginas.
  3. **Metodología del Embudo Progresivo (Sección 4 en [`MANUAL_OPENWEBUI.md`](../MANUAL_OPENWEBUI.md)):**
     - Documentación de la técnica de 4 pasos (*Discovery ➔ GPS ➔ Deep-Dive ➔ Formal Output*) para guiar a modelos compactos locales sin saturar la memoria.
  4. **Saneamiento Integral de Enlaces y Mermaid en GitHub:**
     - Reparación de sintaxis en `README.md` (`flowchart TD` con IDs alfanuméricos) resolviendo el error *"Unable to render rich display"*.
     - Eliminación total de rutas absolutas `file:///home/jose/vllm/` sustituidas por enlaces relativos nativos de GitHub en toda la documentación.
  5. **Formalización del 5to Invariante Operativo MEA v2.1 ([`AGENTS.md`](../AGENTS.md) y [`GEMINI.md`](../GEMINI.md)):**
     - *Invariante de Portabilidad y Prohibición de Rutas Absolutas (Anti-Hardcoded Paths)* para asegurar que el sistema sea 100% reproducible y desacoplado del entorno host.
  6. **Suite de Pruebas Automatizadas:**
     - 19/19 tests unitarios pasando en verde (`Ran 19 tests in 1.539s - OK`) en `tests/test_gateway_core.py` y `tests/test_gateway_tools.py`.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Veracidad 100%, cero destructividad, erradicación de parches y rutas absolutas, y cumplimiento del pacto de consenso mutuo.
  * **Ley 1 (Modularización):** Cumplida al 100%. Módulos de GPS, endpoints, visor y catálogo de pruebas completamente desacoplados.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Resolución estructural de cortes de contexto, enlaces rotos y portabilidad ambiental.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Cambios quirúrgicos, retrocompatibilidad absoluta en APIs y servicios.
  * **RVI Máximo:** `2/10`.

### 🔹 Sesión: 2026-09-01 Madrugada (`bba5ef3a-c9c3-41a0-9e67-95058f9b5fb1`)
* **Hitos Principales:**
  1. **Resolución de Restricción de Memoria KV Cache (Qwen 2.5 7B & Gemma 4 12B):**
     - Diagnóstico matemático del consumo de KV Cache en modelos con Full Causal Attention (Qwen 2.5 7B en BF16 ocupando 14.3 GB con KV Cache de 7.5 GB para 128k = saturación) vs atención híbrida con Sliding Window (Gemma 4 12B en FP8 8-bit ocupando ~12.8 GB con ~3.5 GB para KV Cache en 64K).
     - Inyección de `VLLM_ALLOW_LONG_MAX_MODEL_LEN=1` en [`app.py`](../app.py) para evitar bloqueos por validación Pydantic de longitud y soporte para parser de razonamiento (`qwq` ➔ `--reasoning-parser deepseek_r1`).
  2. **Creación del Submódulo de Alineación Ética y Operativa ([`gateway/core/alignment_engine.py`](../gateway/core/alignment_engine.py)):**
     - Cumplimiento estricto de la **Ley 1 (Modularización Estricta)** y **Ley 2 (Causa Raíz)** desacoplando la manipulación del payload de inferencia de [`gateway/proxy/proxy_factory.py`](../gateway/proxy/proxy_factory.py).
     - **Invariante de Veracidad e Integridad (Gate 1 del MEA):** Erradicación de URLs simuladas (`example.com`) o excusas de "entorno de prueba", forzando la emisión del `tool_call` formal (`generate_pdf_document`).
     - **Invariante de Fidelidad Documental:** Mandato de procesamiento exhaustivo de tablas normativas y categorías operativas (ASC, ASE, ASG) de Teccam.
     - Sincronización temporal determinista en español.
  3. **Persistencia Dinámica en MongoDB (`vllm.alignment_settings`) y Sincronizador en Tiempo Real:**
     - Creación de la colección `alignment_settings` en MongoDB y la función reactiva `sync_alignment_settings_loop()` en el Gateway con 0 ms de overhead de inferencia (caché en memoria local).
     - Implementación de `get_alignment_settings()` y `save_alignment_settings()` con fallback robusto.
  4. **Protección Anti-Desbordamiento de `max_tokens` (Fix de OpenWebUI):**
     - Identificación del bug de cálculo en OpenWebUI donde reclama todo el remanente de la ventana de contexto ($65536 - 8112 = 57424$) causando rechazo en vLLM por 1 solo token de exceso ($8113 + 57424 = 65537$).
     - Implementación de clamping inteligente (`max_response_tokens_cap=8192`) en el Gateway, permitiendo conversaciones continuas de decenas de turnos sin desbordar la ventana.
  5. **Integración Completa en la GUI del Dashboard Web ([`app_dashboard.py`](../app_dashboard.py), [`templates/tabs/tab_alignment.html`](../templates/tabs/tab_alignment.html), [`static/js/dashboard_alignment.js`](../static/js/dashboard_alignment.js)):**
     - Pestaña dedicada **"Alineación y MEA"** con icono de escudo esmeralda en el menú lateral.
     - Switches visuales para control de blindaje, temporalidad, invariantes MEA y protocolos de PDF / Lectura de documentos.
     - Control dinámico de `max_response_tokens_cap`.
     - Editores con tipografía monospace para Invariantes MEA (con botón de restauración rápida) y directivas personalizadas.
     - Endpoints API `/api/alignment/settings` (GET/POST) con feedback visual y aplicación en caliente.
  6. **Validación Práctica End-to-End:**
     - Comprobación empírica en OpenWebUI con generación de PDF ejecutivo de Teccam, verificando la lectura completa en LanceDB y la descarga del PDF con formato profesional.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Veracidad 100% en ejecuciones reales de pruebas, cero destructividad y transparencia absoluta.
  * **Ley 1 (Modularización):** Cumplida al 100%. Desacoplamiento de la lógica de alineación de `proxy_factory.py` en `gateway/core/alignment_engine.py`.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Se resolvió la raíz de la simulación de links en el LLM mediante el prompt guard y el desbordamiento de tokens mediante clamping en el Gateway.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Intervenciones quirúrgicas y modulares preservando todos los servicios existentes intactos.
  * **RVI Máximo:** `2/10`.

### 🔹 Sesión: 2026-08-31 Noche (`b034eae5-9dc4-4b4a-96d1-ea3276b3c9c5`)
* **Hitos Principales:**
  1. **Análisis Epistemológico de Condicionalidad del MEA:** Evaluación del *Efecto Observador / Colapso Cuántico* en entornos con memoria persistente. Se determinó mantener el MEA como piso invariante en desarrollo interactivo y delegar pruebas comparativas a bancos de prueba ciegos y aislados.
  2. **Formalización de Causa Raíz en Cuantización (4-bit vs 8-bit):** Registro en [`docs/MEA_AI_ALIGNMENT.md`](MEA_AI_ALIGNMENT.md) y [`FAQ.md`](../FAQ.md) de la degradación no lineal de los *outliers* de atención en modelos densos de 12B y cómo la cuantización de 8-bit (`LOAD_8_BITS=true`) restablece el tool-calling.
  3. **Diseño de RAG Jerárquico para Documentos Masivos (> 60k tokens):** Especificación de la *Tolerancia Dinámica de Tokens* ($\pm 5\%-8\%$) y el *Mapa Estructural de Partes* ("GPS Documental" con `section_path` y rangos de chunks de LanceDB), encolado para desarrollo en la próxima sesión.
  4. **Control GUI de Cuantización y Preset Gemma 4 12B:** Incorporación del selector `LOAD_8_BITS` y botón de carga rápida `Gemma 4 12B-it (8-Bit / 128K)` en la pestaña *Variables* del Dashboard Web ([`templates/tabs/tab_config.html`](../templates/tabs/tab_config.html) y [`static/js/dashboard_core.js`](../static/js/dashboard_core.js)).
  5. **Perfeccionamiento del Motor PDF (`pdf_engine.py`):** Creación de `clean_markdown_inline` para erradicar restos de asteriscos (`**ASC**` ➔ `ASC`) en celdas de tablas y sustitución de marcas crudas por viñetas tipográficas (`•` / `chr(149)`) con sangría jerárquica.
  6. **Validación End-to-End:** Comprobación empírica en Open-WebUI del documento ejecutivo generado por Gemma 4 12B-it e inspección de su internalización semántica del *Deber de Objeción* y *Fidelidad Documental*.
  7. **Suite de Pruebas Unitarias:** 8/8 tests ejecutados y pasando en verde (`Ran 8 tests in 0.018s - OK`).
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**. Veracidad 100% en ejecuciones reales de pruebas, cero destructividad y transparencia absoluta.
  * **Ley 1 (Modularización):** Cumplida al 100%. Las mejoras de UI y PDF se encapsularon en sus componentes nativos.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Se atacó el origen del formateo de texto en el motor PDF y la cuantización en la inferencia.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Intervenciones atómicas, conservando total compatibilidad.
  * **RVI Máximo:** `2/10`.

### 🔹 Sesión: 2026-08-31 Tarde (`18593369-44c7-4fe1-a2f9-f6706111274d`)
* **Hitos Principales:**
  1. **Interoperabilidad LLM en PDF Gateway:** Incorporación del enrutado público de descarga de 1 parámetro (`/api/tools/pdf/download/{dl_filename}`) manteniendo compatibilidad total con la ruta de 2 parámetros (`{file_id}/{dl_filename}`) para evitar fallos de invocación con modelos como **Gemma 4 12B-it**.
  2. **Resolución Inteligente de Archivos:** Búsqueda por prefijo o sufijo con ordenamiento determinista por `mtime` más reciente en `gateway/tools/pdf_generator.py`.
  3. **Renderizado de Tablas Markdown en PDFs (`pdf_engine.py`):** Implementación del componente nativo `add_table` con cabecera estilizada `#1E293B`, rejilla, fondo zebra `#F8FAFC`, cálculo dinámico de ancho de columnas y control de paginación.
  4. **Procesamiento de LaTeX & Grados:** Limpieza y conversión de expresiones de grados (ej. `1.5^{\circ}C` ➔ `1.5°C`) y operadores matemáticos (`\pm`, `\cdot`, `\le`, `\ge`).
  5. **Configuración Condicional de Cuantización `LOAD_8_BITS`:** Integración en `app.py` para permitir la conmutación fluida de `bitsandbytes` entre 4-bit (por defecto) y 8-bit (`{"load_in_8bit": true}`).
  6. **Suite de Pruebas Unitarias:** 7/7 tests ejecutados y pasados exitosamente en `tests/test_gateway_tools.py`.
* **Evaluación MEA v2.1 & Leyes de Ingeniería:**
  * **Invariantes (Gate 1):** **0 violaciones**.
  * **Ley 1 (Modularización):** Cumplida al 100%.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%.
  * **RVI Máximo:** `2/10`.

### 🔹 Sesión: 2026-08-30 (`b034eae5-9dc4-4b4a-96d1-ea3276b3c9c5`)
* **Hitos Principales:**
  1. Refactorización modular completa del Gateway v2.0 (separación en `gateway/core`, `gateway/tools`, `gateway/cloud`, `gateway/proxy`, `gateway/telemetry`).
  2. Unificación determinista de variables de entorno con `load_dotenv` en la raíz.
  3. Optimización del generador de PDFs (`openwebui_pdf_tool.py`), buscador web y base documental RAG (LanceDB).
  4. Validación en vivo del pipeline completo de Audio (Whisper STT, F5-TTS y PyAnnote Diarización 3.1) con tests automatizados.
  5. Creación del Manual de Open-WebUI ([`MANUAL_OPENWEBUI.md`](../MANUAL_OPENWEBUI.md)).
  6. Implementación de las Tres Leyes de Villaronga y el Marco Ético MEA v2.1 en [`AGENTS.md`](../AGENTS.md), [`GEMINI.md`](../GEMINI.md) y [`docs/MEA_AI_ALIGNMENT.md`](MEA_AI_ALIGNMENT.md).
  7. Incorporación de Modelos Cloud Manuales en el Dashboard Web.
* **Desglose de Llamadas Agénticas (970 Total):**
  * `run_command`: 360 ejecuciones de terminal (pruebas de servicios, cURL, validaciones unitarias).
  * `view_file`: 311 inspecciones de código fuente.
  * `replace_file_content`: 132 ediciones quirúrgicas.
  * `write_to_file`: 54 creaciones de módulos y documentación.
  * `grep_search` / `find_by_name`: 81 búsquedas de patrones y archivos.
  * `search_web`: 13 consultas de documentación técnica.
  * `manage_task` / `schedule`: 10 gestiones de procesos en segundo plano.
* **Evaluación MEA & Leyes de Ingeniería:**
  * **Ley 1 (Modularización):** Cumplida al 100%. Se desmanteló el monolito de 1.743 líneas en submódulos de alta cohesión.
  * **Ley 2 (Causa Raíz):** Cumplida al 100%. Se resolvieron los problemas de entorno en `gateway/__init__.py` y el error `Model '' was not found` identificando el campo vacío en el cliente en lugar de forzar parches en el backend.
  * **Ley 3 (Mínimo Blast Radius):** Cumplida al 100%. Todas las intervenciones mantuvieron cero regresiones en los 8 microservicios.
