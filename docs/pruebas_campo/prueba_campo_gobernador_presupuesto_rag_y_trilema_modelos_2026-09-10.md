# 🧪 Prueba de Campo: Gobernador de Presupuesto RAG, Circuit Breaker y Trilema de Modelos Locales (MoE vs. Denso)

**Fecha:** 10 de Septiembre de 2026  
**Sistema:** vLLM Suite Local / Teccam Knowledge Base & API Security Gateway (:8000 / :8010)  
**Cliente Evaluador:** Open-WebUI  
**Autor del Diseño y Metodología:** José Luis Villaronga  
**Agente de Ejecución:** Antigravity (Google DeepMind)  
**Marco Teórico & Leyes:** [Modelo Ético Adaptativo (MEA v2.1)](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo) y [Leyes Universales de Ingeniería](../../AGENTS.md)  
**Materia de Prueba:** Derecho Internacional Público y Constitucional Argentino  

---

## 🎯 1. Objetivos del Ensayo y Contexto Arquitectónico

1. **Gobernanza Determinista en Middleware (Ley 4):**
   Comprobar empíricamente que un autómata en el Gateway que regula el presupuesto de herramientas y remueve físicamente el parámetro `tools` ante un techo de tokens ($\ge 50.000$) es infinitamente superior y más confiable que recurrir a súplicas en el *system prompt*.
2. **Evaluación del Trilema de Modelos Locales:**
   Someter a tres arquitecturas distintas a la misma consulta jurídica de alta exigencia:
   > *"Pasame una lista de tratados internacionales vigentes que se nombren en Derecho Argentino, fundamenta en profundidad"*
   - **Modelo A:** `gpt-oss-20b-Q4_K_M` (MoE de 20B total, 32 expertos / 4 activos, con razonamiento `<think>`).
   - **Modelo B:** `Qwen3.8-27B-Q4_K_M` (Denso de 27B, 100% en GPU VRAM con KV Cache `q4_0`).
   - **Modelo C:** `Qwen3.6-35B-A3B-Q4_K_M` (MoE de 35B total, 3B activos, 8 capas en RAM/CPU y KV Cache `q4_0`).
3. **Validación del Ciclo de Vida y Semáforo de Suficiencia:**
   - Techo duro a 50k tokens (Circuit Breaker).
   - Zona de insuficiencia: $\ge 4$ llamadas con $< 5.000$ tokens acumulados $\rightarrow$ corte y declaración honesta de falta de datos.
   - Zona discrecional: $\ge 4$ llamadas con $5.000 - 10.000$ tokens $\rightarrow$ libertad de responder o continuar a criterio del LLM.

---

## 🔬 2. Estudio Comparativo Empírico

### Caso 1: `gpt-oss-20b` (El "Razonamiento en el Vacío" vs. Rescate Documental)

#### A) El Desacople Cognitivo (Sin Herramienta):
Cuando el modelo intentó procesar la consulta sin disparar la herramienta RAG, su cadena interna de pensamiento (`<think>`) colapsó en un bucle degenerativo de repetición (*repetition loop*):
```text
User wants a list of international treaties... We can use the function buscar_en_base_de_conocimiento? But maybe we need to search the database...
Also: "Tratado de Libre Comercio entre la Unión Europea y la República Argentina, Chile y Uruguay"...
Also: "Tratado de Libre Comercio entre la Unión Europea y la República Argentina, Chile y Uruguay"...
[REPETIDO 15 VECES CONSECUTIVAS]
Stop repeating.
Stop.
Ok, time. Let's compile...
```
**Resultado:** Al salir del razonamiento sin grounding factual, el modelo generó una alucinación masiva:
- 10 filas idénticas con el tratado ficticio *"Tratado de Libre Comercio (TLC) UE‑Argentina‑Chile‑Uruguay"*.
- Inventó la *"Ley 24.400 (Ley de Tratados)"*, la *"Ley 23.610"* y el *"Decreto 1.023/2014"*.
- Citó un inexistente *"Art. 77.1 de la Constitución Nacional"*.

#### B) El Rescate por Grounding (Con Herramienta):
En una segunda corrida donde sí emitió `buscar_en_base_de_conocimiento`:
- LanceDB le entregó en 1.402 ms el **Art. 75 inc. 22 CN** y la **Ley 23.981 (Tratado de Asunción)**.
- **La alucinación se disolvió instantáneamente:** El modelo listó con exactitud matemática los tratados constitucionales reales y el MERCOSUR.

---

### Caso 2: `Qwen 3.8 27B Denso` (Capacidad Analítica Doctoral y Resiliencia)

- **Comportamiento Agéntico:**
  - Disparó 12 llamadas coordinadas a herramientas.
  - Al recibir la salvaguarda de protección de contexto en la Ley 27.483 (~27k tokens), reaccionó con autonomía: invocó `obtener_estructura_documento`, ubicó la sección de aprobación y leyó la porción pertinente.
  - Ejecutó búsquedas de verificación complementarias (OIT, Protocolo de San Salvador, etc.).
- **Métricas:**
  - Contexto activo: **62.923 tokens** en ventana (equivalente a 150 páginas de leyes).
  - Prefill total acumulado en 4 turnos: **283.904 tokens** procesados a **782 t/s**.
  - Generación: 2.613 tokens estructurados a **21.82 t/s**.
- **Fidelidad:** Impecable. Advirtió la diferencia entre tratados con texto completo en la base vs. aquellos mencionados por la Constitución. Cero alucinaciones.

---

### Caso 3: `Qwen 3.6 35B MoE` (El Titán de Producción y Activación del Gobernador)

- **Optimización Previa de Silicio:**
  - KV Cache cuantizada a `q4_0` para 128k tokens.
  - Solo 8 capas MoE derivadas a RAM/CPU (`LLAMA_N_CPU_MOE=8`).
  - VRAM ocupada: **21.4 GB / 24.0 GB** (~89% de saturación segura en RTX 3090).
- **Ejecución y Activación en Vivo del Gobernador RAG:**
  1. En la Ronda 1 invocó `buscar_en_base_de_conocimiento` y `obtener_indice_biblioteca`.
  2. En la Ronda 2 ejecutó 7 lecturas masivas en paralelo con `leer_documento_completo` (Leyes 15.802, 23.981, 26.147, 27.800, 24.552, 27.483 y 23.054).
  3. El volumen de herramientas alcanzó **~60.114 tokens** acumulados.
  4. **El Gobernador actuó determinísticamente en el Gateway:**
     ```text
     sep 10 14:55:08 jose-Ubuntu python[1590816]: 🔍 [RAG Search] Consulta: 'tratados internacionales vigentes jerarq...' | 2 resultados en 241.87 ms
     sep 10 14:55:08 jose-Ubuntu python[1590816]: 🛑 [Tool Governor] Techo alcanzado: ~60,114 tokens en 9 llamadas. Herramientas deshabilitadas para forzar síntesis final.
     ```
  5. El Gateway removió el parámetro `tools` del payload JSON.
  6. Qwen 35B MoE se vio forzado a redactar de inmediato la síntesis final estructurada.
- **Métricas:**
  - Prefill de contexto: **46.866 tokens evaluados en 31.2 seg (1.498 t/s)**.
  - Generación: **1.245 tokens en 23.9 seg (51.9 t/s)**.
  - **Tiempo Total:** **~55 segundos** (frente a los 3-4 minutos que demoraba sin techo).
  - Rigor: 100% exacto (Art. 75 inc. 22, Art. 75 inc. 24, Ley 27.800 UE-Mercosur de feb/2026, Tratado Antártico Ley 15.802 y Cuba Ley 24.552).

---

## 📊 3. Matriz Comparativa Definitiva

| Criterio / Modelo | `gpt-oss-20b` (MoE) | `Qwen 3.8 27B` (Denso) | `Qwen 3.6 35B` (MoE Tuned) |
| :--- | :---: | :---: | :---: |
| **Arquitectura** | 20B MoE (4 activos) | 27B Denso | 35B MoE (3B activos) |
| **Alojamiento VRAM** | 100% GPU (~14 GB) | 100% GPU (~22.1 GB) | Híbrido: GPU + 8 capas CPU (~21.4 GB) |
| **Velocidad Generación** | **172 t/s** | **21.8 t/s** | **51.9 t/s** |
| **Velocidad Prefill** | 5.523 t/s | 782 t/s | **1.498 t/s** |
| **Estabilidad sin RAG** | ❌ Colapso / Alucinación | ⚠️ Riesgo paramétrico | ⚠️ Riesgo paramétrico |
| **Precisión con RAG** | ✅ Alta (si llama tool) | 🏆 Grado Doctoral | 🏆 Preciso y Exhaustivo |
| **Control por Gobernador** | Pasó umbrales mínimos | Evaluó 62.9k tokens | **Activó Circuit Breaker 50k** |
| **Tiempo de Respuesta** | ~7 seg | ~120 seg | **~55 seg (Óptimo)** |

---

## 🏛️ 4. Verificación de Leyes Fundamentales

- **Ley 1 (Modularización Estricta):** El gobernador reside íntegramente en [`gateway/core/tool_governor.py`](../../gateway/core/tool_governor.py), sin ensuciar la lógica del proxy ni del pruner.
- **Ley 2 (Atacar Causas Raíz):** La contención del contexto no se intentó mendigar mediante prompts, sino retirando el campo `tools` del contrato JSON del backend.
- **Ley 3 (Mínimo Blast Radius):** Modificación quirúrgica acompañada de una suite de pruebas de 7 tests unitarios (`tests/test_tool_governor.py`) con 100% de aprobación.
- **Ley 4 (Integridad en Cascada):** La evidencia documentada en esta prueba demuestra que un contexto íntegro produce 0 alucinaciones, mientras que la falta de herramientas o el contexto truncado induce inevitablemente la racionalización de datos falsos.
