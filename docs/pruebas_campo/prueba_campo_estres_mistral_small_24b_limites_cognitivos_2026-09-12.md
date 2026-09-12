# 🧪 Prueba de Campo: Estrés Multi-Turno con Mistral Small 24B, Límites Cognitivos Agénticos y Validación de Ventana a 88k en RTX 3090

**Fecha:** 2026-09-12  
**Modelo en Inferencia:** `Mistral-Small-3.1-24B-Instruct-2503-Q4_0.gguf` bajo `llama-server` (`llama.cpp`)  
**Hardware:** GPU NVIDIA GeForce RTX 3090 (24 GB VRAM, 384-bit, GDDR6X) + Servidor Linux Ubuntu  
**Componentes Clave:** `vllm-gateway` (FastAPI), `ContextPruner`, `ToolGovernor` (Deduplicador Canónico), `LanceDB` (RAG Teccam), Open-WebUI  
**Archivo de Evidencia:** Chat export `62315af1-f700-4ccf-9584-f4d43c364a8d` (10 turnos) y registros de sistema en `journalctl`  
**Marco Teórico:** [Modelo Ético Adaptativo (MEA v2.1 con Invariantes)](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo) y [Leyes Universales de Ingeniería](../../AGENTS.md)

---

## 🎯 1. Objetivo y Alcance de la Prueba

Tras haber implementado con éxito la **Auto-Guardia RAG de latencia cero** y el **Deduplicador Canónico de Tool Calls** en el Gateway, y tras ajustar la ventana física del motor a **88k tokens (90.112 tokens)** para maximizar la estabilidad de VRAM en la RTX 3090, se sometió al modelo `Mistral-Small-24B-Instruct` a la **batería canónica de estrés multi-turno de 30 consultas jurídicas de alta densidad**.

Los objetivos primarios fueron:
1. **Validar la estabilidad de la ventana física de 88k tokens** bajo carga interactiva continua con el `ContextPruner` activo.
2. **Evaluar la capacidad agéntica de bucle cerrado (*ReAct loop*)** de Mistral Small 24B en turnos acumulativos con recuperación documental autónoma en LanceDB.
3. **Determinar la viabilidad operativa** de este modelo para el rol de asistente jurídico corporativo permanente (`CorpAI-Gen | Legal & Compliance`).

---

## ⚙️ 2. Configuración Completa y Parámetros en RTX 3090

El servicio `vllm-llama.service` fue configurado mediante el lanzador dinámico `llama-srv.sh` con los siguientes parámetros auditados en `/proc/[PID]/cmdline`:

| Parámetro CLI | Valor Configurado | Justificación de Ingeniería |
| :--- | :--- | :--- |
| **Binario** | `llama-server` (b3800+) | Compilado nativo con soporte CUDA 12.x y Flash Attention. |
| **Modelo** | `Mistral-Small-3.1-24B-Instruct-2503-Q4_0.gguf` | Cuantización Q4_0 (~14,2 GB de peso base). |
| **Alias** | `CorpAI-Gen \| Legal & Compliance` | Identificador de servicio expuesto a Open-WebUI y Gateway. |
| **`--ctx-size`** | `90112` (~88k tokens) | Techo físico deliberado para dejar ~3,5 GB de margen libre en VRAM. |
| **`--cache-type-k`** | `q4_0` | Cuantización de Keys en KV Cache (ahorro masivo de VRAM). |
| **`--cache-type-v`** | `q4_0` | Cuantización de Values en KV Cache. |
| **`--jinja`** | Activo | Obligatorio para interpretar la sintaxis oficial de plantillas Jinja. |
| **`--chat-template-file`** | `Mistral-Small-3.2-24B-Instruct-2506.jinja` | Plantilla oficial validada para Tool Calling nativo de Mistral. |
| **`--gpu-layers`** | `999` (Offload 100% GPU) | Todas las capas cargadas en la VRAM de la RTX 3090. |
| **`--parallel`** | `2` | 2 slots independientes para concurrencia o aislamiento. |
| **`--batch-size`** | `4096` | Tamaño de lote lógico para evaluación de prompts extensos. |
| **`--ubatch-size`** | `1024` | Tamaño de micro-lote físico en GPU. |
| **`--flash-attn`** | `on` | Aceleración por Flash Attention 2 y reducción de memoria de atención. |
| **`--load-mode`** | `mlock` | Bloqueo de memoria RAM/VRAM para impedir swapping a disco. |
| **`--threads`** | `8` | 8 hilos CPU para operaciones de soporte fuera de CUDA. |
| **`--reasoning`** | `off --no-reasoning-preserve` | Desactivación de tokens de pensamiento superfluos en prompts. |
| **Puerto Backend** | `18100` | Comunicación interna con el API Gateway (puerto 8000). |

### Huella de Memoria Medida en Dashboard:
* **Uso de VRAM (RTX 3090 24 GB):** **`20.5 GB / 24.0 GB`** (**`85.37%`**).
* **Margen Libre de VRAM:** **`~3.5 GB`**, erradicando por diseño cualquier posibilidad de desborde por fragmentación de memoria (*CUDA Out of Memory*).

---

## 📋 3. Batería de Preguntas del Benchmark (30 Consultas Jurídicas)

Para garantizar la reproducibilidad exacta del ensayo, a continuación se detalla la secuencia íntegra de 30 consultas utilizadas en el estrés:

1. **T1:** *¿Qué forma de gobierno adopta la Nación Argentina según el artículo 1 de la Constitución Nacional?*
2. **T2:** *¿Cuáles son los requisitos constitucionales para ser miembro de la Corte Suprema de Justicia de la Nación?*
3. **T3:** *¿Cuál es el mecanismo establecido en la Constitución Nacional para reformar la Carta Magna?*
4. **T4:** *¿Qué es un decreto de necesidad y urgencia (DNU) y cuáles son sus límites según la Constitución y la jurisprudencia?*
5. **T5:** *¿Qué condiciones deben cumplirse para que un acto administrativo de alcance particular y uno de alcance general adquieran eficacia?*
6. **T6:** *¿Cuál es la función del Defensor del Pueblo en el ordenamiento jurídico argentino?*
7. **T7:** *Según la Ley de Procedimiento Administrativo (N° 19.549), ¿cuál es el plazo máximo para evacuar informes administrativos no técnicos?*
8. **T8:** *¿Cómo define el Código Civil y Comercial de la Nación el concepto de "persona humana" y cuáles son sus atributos?*
9. **T9:** *¿Cuáles son los derechos personalísimos reconocidos por el Código Civil y Comercial?*
10. **T10:** *¿Cómo se regula el consentimiento informado para actos médicos e investigaciones en salud según el Código Civil y Comercial?*
11. **T11:** *¿Qué efectos jurídicos produce el matrimonio en relación con los bienes y cuáles son las causales de nulidad absoluta y relativa?*
12. **T12:** *¿Cómo se regulan las obligaciones de dar sumas de dinero en moneda extranjera tras las reformas recientes?*
13. **T13:** *¿Qué tipos de personas jurídicas privadas reconoce el Código Civil y Comercial y cuál es el régimen de responsabilidad de sus administradores?*
14. **T14:** *¿Cómo se articulan las normas del Código Civil y Comercial con la Ley de Defensa del Consumidor (Ley 24.240) en materia de contratos de consumo?*
15. **T15:** *¿Qué modificaciones introdujo el DNU 70/2023 en el régimen de locaciones urbanas del Código Civil y Comercial?*
16. **T16:** *¿Cuáles son las notas tipificantes de la relación de dependencia laboral según la Ley de Contrato de Trabajo (N° 20.744)?*
17. **T17:** *¿Cómo se calcula la indemnización por antigüedad o despido incausado según el artículo 245 de la LCT y qué topes aplican?*
18. **T18:** *¿Cuál es el régimen legal de la jornada de trabajo y los descansos semanales según la Ley 11.544 y la LCT?*
19. **T19:** *¿Qué reformas introdujo la Ley de Bases (Ley 27.742) en el régimen laboral argentino (fondo de cese, período de prueba, presunción de laboralidad)?*
20. **T20:** *¿Cómo opera la protección de la maternidad y la estabilidad de la mujer embarazada en la Ley de Contrato de Trabajo?*
21. **T21:** *¿Qué es el régimen de teletrabajo (Ley 27.555) y cuáles son los derechos esenciales del trabajador bajo esta modalidad?*
22. **T22:** *¿Cuáles son los presupuestos de la responsabilidad civil y cómo se distingue la responsabilidad contractual de la extracontractual en el CCyC?*
23. **T23:** *¿Qué figuras delictivas integran los delitos contra la propiedad en el Código Penal y cuáles son los agravantes del robo?*
24. **T24:** *¿Puede el Presidente de la Nación, a través de un DNU, aumentar la pena prevista en el Código Penal para un delito? Fundamentar.*
25. **T25:** *¿En qué consiste el principio de lesividad (artículo 19 de la Constitución Nacional) y cuál es su impacto en el derecho penal sustantivo?*
26. **T26:** *¿Cuál es el régimen legal de la legítima defensa según el artículo 34 inciso 6 del Código Penal?*
27. **T27:** *¿Qué establece la Ley de Identidad de Género (Ley 26.743) respecto a la rectificación registral del sexo y cambio de nombre?*
28. **T28:** *¿Qué presupuestos mínimos establece la Ley de Glaciares (Ley 26.639) para la protección del ambiente periglacial y qué actividades prohíbe?*
29. **T29:** *¿Qué consecuencias jurídico-penales derivan del incumplimiento de la Ley Nicolás (Ley 27.797) de Calidad y Seguridad Sanitaria? [Pregunta trampa]*
30. **T30:** *¿Qué modificaciones introdujo el Decreto 70/2025 a la Ley de Identidad de Género? [Pregunta trampa]*

---

## 🔬 4. Autopsia Forense de los 10 Turnos Ejecutados

El modelo ejecutó 9 turnos de diálogo y **colapsó definitivamente en el Turno 10**. A continuación se exponen los datos duros de cada interacción:

| Turno | Pregunta | Tokens Prompt | Herramientas Llamadas | `doc_id` Invocado | Resultado / Dictamen |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **T1** | Forma de gobierno (Art. 1 CN) | 16.962 | 4 (RAG + Web) | `6a976eb89e1c2342dd2e5b34` (404) | ❌ Copió ID de docstring; no vio la CN en catálogo; llamó a Web. |
| **T2** | Jueces Corte Suprema | 18.850 | 1 | `6aa2af17a90fa60634db979a` (CN) | 🟢 Preciso (recuperó Art. 111 de la CN). |
| **T3** | Reforma de la Constitución | 20.766 | 1 | `6aa2af17a90fa60634db979a` (CN) | 🔴 **Alucinación Grave:** Como Art. 30 no vino en top 4, afirmó que el **Art. 41** (ambiental) reforma la CN. |
| **T4** | DNU y límites | 23.685 | 1 | `6aa2af17a90fa60634db979a` (CN) | 🟢 Preciso (Art. 99 inc. 3). |
| **T5** | Actos administrativos | 26.273 | 1 | `6a977abb9e1c2342dd2e5b43` (Tributario) | 🟡 Buscó en Ley Tributaria en vez de Ley 19.549; respondió de memoria paramétrica. |
| **T6** | Defensor del Pueblo | 29.093 | 1 | `6aa2af17a90fa60634db979a` (CN) | 🟢 Preciso (Art. 86). |
| **T7** | Plazo informes no técnicos (19.549) | **11.526** *(Poda T1)* | 1 | `6a8b02cface6becbcb49b20d` (Cód. 1869) | 🔴 **Fractura ReAct:** Buscó en Código Civil Derogado de 1869; prometió buscar de nuevo y **cortó el turno sin llamar tools**. |
| **T8** | Persona humana en CCyC | **9.951** *(Poda T2)* | 2 | `6a976eb89e1c2342dd2e5b34` (404) | 🔴 **Fractura ReAct:** Volvió al ID de docstring; prometió buscar en biblioteca y **cortó el turno sin llamar tools**. |
| **T9/10** | Derechos personalísimos | **4.785** *(Poda T3)* | 0 | *(Ninguno)* | 🛑 **Colapso Total (Tarea 7033):** Bucle generativo infinito (**5.940 tokens en 2m37s**). Socket cerrado por timeout. |

---

## 💥 5. Análisis de Causa Raíz de las 4 Fracturas Cognitivas

El examen exhaustivo de los logs demuestra que el colapso no fue producto de un bug de software ni de hardware, sino de una **incompatibilidad estructural en el modelado cognitivo de Mistral Small 24B**:

### 1. Literalismo Ciego de Docstring (*Hardcoded Example Bias*)
En los Turnos 1 y 8, el modelo pobló el parámetro `doc_id` con el valor exacto `"6a976eb89e1c2342dd2e5b34"`.  
Al auditar el código fuente de `tools/openwebui_rag_tool.py` se constató:
```python
:param doc_id: Opcional: ID de la obra (ej: '6a976eb89e1c2342dd2e5b34' para CCCN)...
```
Mistral es incapaz de discernir entre un ejemplo pedagógico y un dato operativo dinámico. Replicó el ID de ejemplo literalmente para la Constitución y para el Código Civil, derivando en excepciones HTTP 404.

### 2. Violación de la Ley 4: Alucinación Sustitutiva ante el Vacío Semántico
* **Amnesia de Catálogo (Turno 1):** Invocó `obtener_indice_biblioteca` y recibió la lista completa donde figuraba explícitamente `CONSTITUCION DE LA NACION ARGENTINA Ley Nº 24.430`. El modelo leyó la lista y afirmó: *"En la base de conocimiento no está disponible..."*, forzando una llamada innecesaria a Internet.
* **Alucinación Normativa Extrema (Turno 3):** Al consultar el mecanismo de reforma constitucional, la búsqueda semántica recuperó el Preámbulo, Art. 1, Art. 5 y Art. 75, omitiendo el Art. 30. Un modelo agéntico maduro explora el índice o busca por número de artículo. Mistral, en cambio, **inventó que el Artículo 41 (que protege el medio ambiente sano) era la norma que exigía dos tercios del Congreso para reformar la Carta Magna**. En un entorno corporativo y jurídico, esto representa una alucinación inaceptable.

### 3. Ruptura del Paradigma ReAct: Degeneración Metadiscursiva (*Narrative Looping*)
A partir del Turno 7, al encontrarse con resultados derogados o inexistentes, el modelo abandonó el ciclo de ejecución de herramientas:
* **Turno 7:** *"La búsqueda no devolvió contenido relevante... Por ello, procederé a ejecutar nuevamente una búsqueda de la normativa vigente en la base de conocimientos."* $\rightarrow$ **Cerró el turno sin invocar ninguna función.**
* **Turno 8:** *"Para proporcionar una respuesta precisa, se ejecutará una búsqueda en la biblioteca para verificar si el Código Civil y Comercial está disponible..."* $\rightarrow$ **Volvió a cerrar el turno en falso.**

El modelo dejó de actuar como un agente ejecutor y pasó a ser un relator que narra sus intenciones futuras en tercera persona, dejando al usuario sin respuesta.

### 4. El Bucle Desbocado de la Tarea 7033 (Turno 10)
Al llegar la consulta sobre *Derechos personalísimos*, el historial acumulado en la ventana del `ContextPruner` contenía dos turnos consecutivos donde el propio asistente hablaba de "ejecutar búsquedas a futuro".  
En la arquitectura autorregresiva de Mistral, este patrón actuó como un atractor probabilístico dominante. El motor `llama-server` registró:
```text
sep 12 11:54:52 llama-server: task 7033 | processing task
sep 12 11:55:03 llama-server: task 7033 | n_gen =  247, tg = 40.80 t/s
...
sep 12 11:57:27 llama-server: task 7033 | n_gen = 5940, tg = 39.44 t/s
sep 12 11:57:29 llama-server: stop: cancel task, id_task = 7033 (client disconnect)
```
El modelo quedó atrapado en una generación infinita de texto/tokens, emitiendo **5.940 tokens durante 2 minutos y 37 segundos a 40 tokens/segundo** sin emitir jamás el token de parada (`EOS` / `[DONE]`), hasta que el cliente Open-WebUI abortó la conexión por inactividad.

---

## 📊 6. Validación Definitiva: La Ventana a 88k Queda 100% Absuelta

La prueba de estrés refuta taxativamente cualquier sospecha sobre el límite de contexto a 88k:
1. **Consumo Real de Tokens:** El colapso se produjo con apenas **4.785 tokens de prompt** en el Turno 10 (**5.4% de la ventana de 88k**).
2. **Efectividad del Podador:** El `ContextPruner` mantuvo la conversación acotada en todo momento (29k $\rightarrow$ 11.5k $\rightarrow$ 9.9k $\rightarrow$ 4.7k tokens), liberando memoria de slots continuamente.
3. **Estabilidad Térmica y de VRAM:** Durante las más de 12 horas de ejecución continua, la RTX 3090 operó en **49°C a 55°C** con **20.5 GB de VRAM**, sin un solo pico de saturación ni error de CUDA.

Reducir la ventana nominal a 88k fue una **decisión de ingeniería 100% exitosa**, preservando 3.5 GB de colchón de seguridad sin perjudicar la inferencia.

---

## ⚖️ 7. Comparativa de Modelos en el Mismo Banco de Pruebas

| Criterio de Evaluación | `gpt-oss-20b` (GGUF Q4) | `Qwen 2.5 32B / 3.6 MoE` | `Gemma 4 12B` | `Mistral-Small-24B` |
| :--- | :---: | :---: | :---: | :---: |
| **Resolución del Estrés 30 Turnos** | 🟢 **100% Completo (31/31)** | 🟢 **100% Completo** | 🟢 **100% Completo** | 🔴 **Falló en Turno 10** |
| **Adherencia ReAct (Bucle Tools)** | Alta (recupera errores) | Excelente (robusto) | Rigurosa | 🔴 Baja (cae en relato) |
| **Resistencia a Alucinación Normativa** | Alta (declara ausencia) | Alta | Muy Alta (purismo MEA) | 🔴 Baja (inventa artículos) |
| **Síntesis Analítica One-Shot** | Media | Alta | Alta | 🟢 **Extraordinaria** |
| **Compatibilidad `llama.cpp` Stream** | Nativa directa | Nativa directa | Nativa directa | 🟡 Requiere Middleware |
| **VRAM en RTX 3090 (24 GB)** | 16.5 GB | 18.2 – 21.0 GB | 12.5 GB | 20.5 GB |

---

## 🏛️ 8. Conclusiones y Veredicto Arquitectónico

1. **La Paradoja de Mistral Small 24B:**  
   Es un modelo con una capacidad de síntesis y razonamiento deductivo excepcional para consultas aisladas complejas (como demostró en la descomposición de 4 llamadas del caso Antártico/Glaciares), pero carece de la estabilidad agéntica necesaria para interactuar en bucle cerrado a lo largo de sesiones conversacionales extensas.
2. **Costo de Gobernanza Excesivo:**  
   El esfuerzo de ingeniería para contener a Mistral mediante parches de transporte, auto-guardias de JSON crudo, deduplicadores y detectores de relato en prosa no compensa su inestabilidad en producción frente a arquitecturas con mejor alineación ReAct nativa.
3. **Recomendación Estratégica:**  
   Consolidar la infraestructura del Gateway y la ventana calibrada a **88k tokens con VRAM en 20.5 GB**, reservando Mistral para tareas específicas de procesamiento analítico por lotes (*batch synthesis*) y devolviendo el rol de agente conversacional interactivo a modelos agénticamente templados como **Qwen 2.5/3.6** o **Gemma 4**.
