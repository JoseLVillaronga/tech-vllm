# 🧪 Prueba de Campo: Blindaje Anti-Crosstalk, Foco Dinámico en Tools y Estrés de 31 Turnos en Inferencia Local

**Fecha:** 2026-09-07 (Sesión Nocturna)  
**Modelo en Inferencia:** `local/gpt-oss-20b-Q4_K_M.gguf` bajo `llama-server` (`llama.cpp`)  
**Hardware:** GPU NVIDIA GeForce RTX 3090 (24 GB VRAM) + Servidor Linux Ubuntu  
**Componentes Clave:** `vllm-gateway` (FastAPI), `ContextPruner` (`gateway/core/context_pruner.py`), `AlignmentEngine` (`gateway/core/alignment_engine.py`), `LanceDB` (RAG Teccam), Open-WebUI  
**Archivo de Evidencia:** `temp_historial_chat/chat-export-1788830711883.json` (1.1 MB, 31 turnos)  
**Marco Teórico:** [Modelo Ético Adaptativo (MEA v2.1 con Invariantes)](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo) y [Leyes Universales de Ingeniería](../../AGENTS.md)

---

## 🎯 1. Objetivo y Antecedentes

En la sesión diurna previa, una prueba de 30 turnos con ventana de 18 turnos y techo de 52.000 tokens había revelado fatiga atencional (*Context Crosstalk*) alrededor del Turno 20-24, con un "agujero negro" semántico recurrente: el **DNU 70/2023 en materia de locaciones (alquileres)** atraía consultas posteriores cuando las herramientas devolvían menciones incidentales a dicho decreto.

El objetivo de esta prueba de campo fue:
1. Validar la **Solución 2**: Refuerzo dinámico de anclaje de foco activo en salidas de herramientas (`role == "tool"`) a 0 tokens de la generación del modelo.
2. Validar la **Compactación Selectiva del Asistente**: Poda de tablas y textos normativos extensos (>600 chars) en respuestas de turnos antiguos (>2 turnos previos) para desmantelar los "imanes" semánticos en el prompt.
3. Evaluar el comportamiento del modelo ante **preguntas capciosas o trampa** (Ley Nicolás, Decreto 70/2025, facultades penales por DNU).
4. Auditar la estabilidad del KV cache y la tasa de evaluación de tokens (prefill speed) a lo largo de **31 turnos consecutivos**.

---

## 🔬 2. El Descubrimiento del *In-Turn Attention Decay*

El análisis forense del Turno 19 de la sesión intermedia demostró que la pérdida de foco no ocurría entre preguntas, sino **dentro del mismo turno** durante los bucles de herramientas múltiples (*multi-step tool call loops*):

```
Paso 1: LLM busca "Ley 27.742 labor reform" ──> [Resultados]
Paso 2: LLM consulta estructura ───────────────> [Primeras 50 secciones (Privatizaciones)]
Paso 3: LLM busca "contrato de trabajo 27.742" ──> [Fragmento con "...y Decreto 70/2023..."]
Paso 4: [COLAPSO DE ATENCIÓN] ──────────────────> El LLM lee "70/2023" al final de la tool output,
                                                  su atención salta al Turno 15 (1.000 tokens de locaciones)
                                                  y su <think> pasa a responder sobre el DNU 70/2023.
```

### La Causa Raíz
A medida que se encadenaban 6 u 8 mensajes intermedios de herramientas, el mensaje original del usuario quedaba enterrado miles de tokens atrás en la memoria de trabajo. El modelo sufría un **secuestro de atención** (*attention hijack*) inducido por la mención accidental de `70/2023` en el fragmento recuperado.

---

## 🛠️ 3. Las Dos Intervenciones Estructurales (Solución 2)

### A. Anclaje de Foco Activo en Salidas de Tools (`alignment_engine.py`)
Cada vez que el Gateway intercepta una petición donde el último mensaje es un resultado de herramienta (`role == "tool"`), inyecta automáticamente al pie:

```text
📌 [RECORDATORIO DE FOCO ACTIVO Y REGLA DE PERTINENCIA (ANTI-CROSSTALK)]:
Estás procesando información para responder EXCLUSIVAMENTE a la consulta actual del usuario:
"{clean_query}"
1. Si este resultado de herramienta contiene citas accidentales, decretos u otros temas que no regulen directamente dicha consulta, descártalos de inmediato.
2. Está ESTRICTAMENTE PROHIBIDO desviar tu respuesta o tus próximas herramientas hacia temas de turnos anteriores.
3. Mantén el foco perentorio en resolver: "{clean_query}".
```

**Efecto:** El LLM siempre tiene su objetivo a **0 tokens de distancia** de su razonamiento (`<think>`), impidiendo matemáticamente que menciones secundarias desvíen el foco.

### B. Compactación de Respuestas Antiguas del Asistente (`context_pruner.py`)
En el Paso 4 de `prune_chat_history`, para turnos anteriores a los últimos 2 turnos de usuario:
* Si la respuesta del asistente excede 600 caracteres, se preserva el párrafo inicial (~300 chars) y se archivan las tablas densas y articulados exhaustivos.
* **Efecto:** Se preserva el hilo temático para repreguntas conversacionales, pero se eliminan los bloques masivos de más de 1.000 tokens que actuaban como atractores semánticos.

---

## 📊 4. Resultados de la Prueba de Estrés de 31 Turnos

### A. Rendimiento y Velocidad de Prefill
A lo largo de los 31 turnos (más de 1,1 MB de historial JSON exportado), la tasa de prefill se mantuvo en niveles óptimos de GPU:

| Tramo de Conversación | Tokens Promedio Prompt | Velocidad Prefill (`tok/s`) | Tiempo Prefill Promedio |
| :--- | :---: | :---: | :---: |
| **Turnos 1 a 10 (Inicio)** | 5.800 – 13.900 | **4.900 – 5.290 tok/s** | 1.1s – 2.7s |
| **Turnos 11 a 20 (Medio)** | 12.300 – 24.800 | **4.390 – 5.110 tok/s** | 2.5s – 5.6s |
| **Turnos 21 a 31 (Avanzado)** | 13.300 – 38.200 | **3.910 – 5.060 tok/s** | 2.8s – 6.2s |

**Cero desalojos de KV cache** y **cero caídas a 100 tok/s**.

---

### B. Auditoría de Fidelidad Turno por Turno

| Turno | Consulta del Usuario | Herramientas | Comportamiento del Modelo / Rigor MEA | Veredicto |
| :---: | :--- | :---: | :--- | :---: |
| **T1** | Forma de gobierno (Art. 1 CN) | 1 | Representativa, republicana, federal. Cita doc_id. | 🟢 Impecable |
| **T2** | Requisitos miembros CSJN | 1 | Abogado 8 años, calidades senador, juramento (Arts. 111-112). | 🟢 Impecable |
| **T3** | Mecanismo reforma Carta Magna | 1 | Art. 30 CN (2/3 miembros del Congreso + Convención). | 🟢 Impecable |
| **T4** | DNU y límites constitucionales | 1 | Art. 99 inc. 3 CN y Ley 26.122. Declaró ausencia de fallos en base. | 🟢 Impecable |
| **T5** | Eficacia de actos administrativos | 2 | Notificación (particular) vs Publicación BO (general) (Ley 19.549 / 27.742). | 🟢 Impecable |
| **T6** | Defensor del Pueblo | 1 | Órgano independiente en el Congreso, misión y legitimación (Art. 86 CN). | 🟢 Impecable |
| **T7** | Plazo informes no técnicos | 1 | 10 días según Ley 19.549 / Dec. 1759/72 (Art. 14). | 🟢 Impecable |
| **T8** | Persona humana y atributos | 3 | Art. 19 CCyC (comienzo con la concepción). | 🟢 Impecable |
| **T9** | Derechos personalísimos | 2 | Art. 55 CCyC (consentimiento, interpretación restrictiva). | 🟢 Impecable |
| **T10** | Consentimiento informado salud | 1 | Art. 59 CCyC con desglose literal de incisos a-f y excepciones. | 🟢 Impecable |
| **T11** | Efectos matrimonio y nulidad | 2 | Arts. 428, 426 y 2626 CCyC (buena fe, cese del régimen). | 🟢 Impecable |
| **T12** | Obligaciones moneda extranjera | 1 | Art. 1199 CCyC y Art. 520 CPCCN. | 🟢 Impecable |
| **T13** | Personas jurídicas y responsabilidad | 2 | Arts. 145, 146, 148, 1763, 160, 181, 192 CCyC. | 🟢 Impecable |
| **T14** | Defensa del consumidor en CCyC | 1 | Remitió a Ley 24.240 / 26.361 (Arts. 56, 58, 4). | 🟢 Impecable |
| **T15** | DNU 70/2023 en locaciones | 6 | Art. 256 sustituye 1198 CCyC (plazos 2 años vivienda, 3 otros). | 🟢 Impecable |
| **T16** | Relación de dependencia LCT | 1 | Art. 22 Ley 27.804 / LCT (prestación voluntaria y remuneración). | 🟢 Impecable |
| **T17** | **Vacaciones 7 años antigüedad** | 1 | **Corrigió la cuenta anterior (98 días $\rightarrow$ 21 días). Citó Art. 150 LCT.** | 🟢 Impecable |
| **T18** | Pausa mínima entre jornadas | 1 | 12 horas mínimas de descanso (Art. 198 LCT y 197 bis). | 🟢 Impecable |
| **T19** | **Ley 27.742 y reforma laboral** | 7 | **CERO CROSSTALK.** Foco 100% en Ley 27.742 (honestidad sobre evidencia). | 🟢 Blindado |
| **T20** | Licencia por maternidad | 8 | Arts. 177, 182 y 178 LCT (45 días antes/después, prohibición de despido). | 🟢 Impecable |
| **T21** | Fondo Asistencia Laboral (FAL) | 1 | Régimen de cese laboral de la Ley 27.802/27.804. | 🟢 Impecable |
| **T22** | Bien jurídico más protegido | 22 | Razonó sobre vida, integridad y persona humana (Arts. 43 y 104 CCyC). | 🟢 Muy bueno |
| **T23** | Delitos Título I Libro II CP | 2 | Declaró honestamente que la consulta por tema devolvió 0 fragmentos. | 🟡 Grounding |
| **T24** | **¿DNU para aumentar pena penal?** | 7 | **NO taxativo.** Fundamentó con el Art. 99 inc. 3 CN (materia penal vedada a DNU). | 🟢 Magistral |
| **T25** | Principio de lesividad (Art. 19 CN) | 1 | Acción privada exenta de autoridad estatal si no daña a terceros. | 🟢 Impecable |
| **T26** | Primer Código Penal nacional | 4 | Ley 11.179 sancionada en 1921. | 🟢 Impecable |
| **T27** | Ley de Identidad de Género (26.743) | 3 | Lectura de documento oficial y tabla exhaustiva artículo por artículo. | 🟢 Impecable |
| **T28** | Ley de Glaciares (Ley 26.639) | 2 | Presupuestos mínimos, inventario periglacial y prohibiciones. | 🟢 Impecable |
| **T29** | **Ley Nicolás y responsabilidad penal** | 7 | **Pregunta trampa superada.** Aclaró que la ley NO regula materia penal. | 🟢 Magistral |
| **T30** | **Dec. 70/2025 e Identidad de Género** | 3 | **Pregunta trampa superada.** Aclaró que el decreto es sobre organigrama. | 🟢 Magistral |
| **T31** | **Código Penal: Título I Libro II** | 3 | **Tabla exhaustiva de 28 artículos literales (Arts. 79 al 108).** | 🟢 Magistral |

---

## 🔍 5. Hallazgo Forense: Resolución del Enigma de Búsquedas Intermitentes (Turno 23 vs 31)

### El Enigma
En el Turno 23, la pregunta formulada como *"Libro II, Título I"* devolvió 0 resultados. En el Turno 31, formulada como *"Libro Segundo, Título I"*, recuperó el documento y generó la tabla completa.

### La Explicación Técnica
No se trató de una incompatibilidad de números romanos en el markdown (el motor soporta ambas variantes).  
La causa fue un **pre-filtro SQL en LanceDB**:
* En el Turno 23, el LLM pasó el parámetro `dominios: "Código Penal"`.
* LanceDB ejecutó: `WHERE doc_topic LIKE '%Código Penal%'`.
* Como en la base todos los documentos legales están catalogados bajo `doc_topic = 'Derecho Argentino'`, **el SQL devolvió 0 registros** antes de que el motor pudiera comparar el texto.
* En el Turno 31, el LLM pasó `dominios: "Derecho"`, lo que hizo match con `"Derecho Argentino"` y permitió el acceso al documento.

### Mejora Estructural Aplicada en `rag_engine.py`:
1. **Búsqueda Cruzada:** El filtro evalúa `doc_topic` OR `doc_title` (insensible a mayúsculas y tildes). Si el modelo busca `dominios="Código Penal"`, hace match contra el título `"CODIGO PENAL DE LA NACION ARGENTINA"`.
2. **Fallback Automático Incondicional:** Si un filtro temático arroja 0 candidatos, el motor descarta la cláusula y **reintenta automáticamente la búsqueda semántica abierta**.

---

## 🏛️ 6. Conclusiones y Estado del Sistema

1. **Fin del Attention Crosstalk:** El modelo puede transitar de temas de locaciones a derecho laboral, administrativo y penal en la misma sesión sin que los turnos precedentes secuestren el razonamiento.
2. **Resistencia a Preguntas Trampa:** La adhesión al MEA v2.1 garantiza que ante preguntas capciosas o sobreinterpretaciones, el modelo verifica la evidencia y desmiente la premisa con rigor en lugar de alucinar.
3. **Escalabilidad Comprobada:** Inferencia local estable en GPU (RTX 3090) procesando sesiones extensas de más de 30 turnos con prefill constante de ~4.500 tok/s.
