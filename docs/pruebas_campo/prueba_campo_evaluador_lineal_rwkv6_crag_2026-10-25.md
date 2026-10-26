# 🧪 Prueba de Campo: Evaluación Deductiva CRAG con Atención Lineal (RWKV-6 Finch 7B) y Disyuntor Anti-Bucle Inter-Rondas

**Fecha:** 2026-10-25 (Sesión Noche)  
**Entorno:** Ubuntu Linux (RTX 3090 24GB + i9-14900K 64GB)  
**Modelo de Referencia:** `twil-lm3-q4_k_m.gguf` (SmolLM3 3.1B Logic/Reasoning, JSON ChatML en `:18300`)  
**Modelo Lineal Adoptado:** `v6-Finch-7B-HF-Q5_K_M.gguf` (RWKV-6 Architecture, Booleano `/completion` en `:18300`)  
**Módulos de Producción:** `rag/evaluator.py`, `gateway/core/tool_governor.py`, `llama-evaluator-srv.sh`  
**Laboratorio de Pruebas:** `lab_linear_evaluator/bench_rwkv_evaluator.py`  
**Autor:** José Luis Villaronga  
**Agente Operativo:** Antigravity (Google DeepMind)  

---

## 1. Motivación y Causa Raíz

### 1.1. El Cuello de Botella del Evaluador CRAG Basado en Transformers
En la arquitectura RAG de Teccam, el evaluador de suficiencia documental (CRAG) valida si la evidencia recuperada por las herramientas (`buscar_en_base_de_conocimiento` o `leer_documento_completo`) contiene información suficiente y concluyente para responder a la consulta del usuario sin inducir alucinaciones ni recurrir a memoria paramétrica viciada (Ley 4).

Con modelos Transformer autorregresivos tradicionales (como `twil-lm3-q4_k_m`):
1. **Crecimiento de Memoria $\mathcal{O}(N)$ y VRAM:** El cálculo de atención cuadrático y la asignación dinámica de KV Cache crecen con el tamaño del contexto.
2. **Latencia y Truncamiento Ciego:** Para evitar latencias prohibitivas ($>700$ ms) y riesgos de contención de memoria frente al LLM principal (Qwen 3.6 35B MoE), el contexto debía truncarse agresivamente a 5.000 caracteres.
3. **Pérdida de Integridad:** Un truncamiento en 5.000 caracteres impide evaluar capítulos extensos de leyes o tratados consolidados (como el Código Civil y Comercial de la Nación).

### 1.2. Hipótesis Operativa
Validar si un modelo basado en **Atención Lineal / State-Space Model (RWKV-6 Finch)** permite:
1. Operar con memoria de estado constante $\mathcal{O}(1)$ independientemente de la longitud de la ventana (admitiendo hasta 30.000+ caracteres de evidencia sin crecimiento dinámico de memoria).
2. Reducir la latencia de evaluación por debajo de los 250 ms.
3. Alcanzar paridad o superioridad en precisión deductiva frente a `twil-lm3` en descarte de distractores y validación booleana.

---

## 2. Aislamiento y Metodología Experimental (Leyes 1 y 3)

Se creó el laboratorio modular independiente `lab_linear_evaluator/bench_rwkv_evaluator.py` sin alterar el flujo de producción durante la fase de benchmarking.

### 2.1. Harness de Evaluación NLI / CRAG (10 Casos de Prueba Rigurosos)
Se diseñó una batería de pruebas de inferencia lógica que evaluó:
* **Verdaderos Positivos Claros:** Definición de contrato de trabajo (LCT), quorum de asamblea, prescripción de daños.
* **Falsos Positivos por Distracción Léxica (Trampas de Mención Superficial):** Fragmentos que mencionan palabras clave de la pregunta (ej: "tratado", "Argentina", "sociedades") pero carecen del dato específico demandado (fechas de ratificación, quorums, etc.).
* **Falsos Positivos por Coincidencia Parcial:** Textos de leyes tangenciales que no responden a la doctrina consultada.

---

## 3. Benchmark Empírico de Modelos Candidatos (RTX 3090)

Se descargaron y evaluaron 5 pesos candidatos en `llama.cpp` (puerto `:18300`):

| Modelo Candidato | Formato / Cuant. | Precisión NLI (10 casos) | Latencia Media | VRAM Asignada | Diagnóstico Operativo |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`RWKV-v6-World-1.6B`** | `Q4_K_M` | 40% (4/10) | 145 ms | 1.85 GB | **Rechazado.** Sesgo severo de complacencia (*sycophancy*); incapacidad de rechazar distractores léxicos. |
| **`v6-Finch-3B-HF`** | `Q8_0` | 40% calib. (4/10) | 165 ms | 3.42 GB | **Rechazado.** Sobre-asociación léxica. Ante la palabra "Argentina", afirmaba suficiencia aunque el texto tratara de geografía. |
| **`v6-Finch-7B-HF`** | `Q4_0_8_8` | N/A (Fallo de carga) | N/A | N/A | **Incompatible.** Error `TYPE_Q4_0_8_8 REMOVED` en `llama.cpp` (formato experimental ARM NEON discontinuado). |
| **`v6-Finch-14B-HF`** | `Q2_K` | 60% (6/10) | 460 ms | 23.8 GB (Pico) | **Rechazado.** Cuantización destructiva de 2 bits en el estado recurrente causó pérdida sintáctica (*"prescipriondo de daos"*). Riesgo inminente de OOM en GPU compartida. |
| **`v6-Finch-7B-HF`** | `Q5_K_M` | **100% (10/10)** | **214 ms** | **5.65 GB** | 🏆 **Aprobado.** Cero fallos deductivos, rechazo perfecto de trampas léxicas, 3.2x más rápido que `twil-lm3`. |

---

## 4. Hallazgos Teóricos y de Arquitectura Recurrente

### 4.1. Fragilidad del Vector de Estado Recurrente ante Cuantización Agresiva ($<4$ bits)
En modelos Transformer, la cuantización `Q2_K` afecta los pesos de proyección, pero las activaciones se recalculan de forma aislada por capa. En redes recurrentes lineales (RWKV-6):
$$h_t = W_k h_{t-1} + k_t v_t$$
Un error de precisión de 2 bits en el operador de recurrencia se acumula de forma exponencial a lo largo de los pasos temporales, degradando la memoria de trabajo y provocando el colapso del estado latente. La cuantización de 5 bits (`Q5_K_M`) demostró ser el límite óptimo de fidelidad matemática.

### 4.2. Umbral de Masa Crítica para NLI en Español
Los modelos recurrentes por debajo de 7B (1.6B y 3B) carecen de la capacidad representacional para desacoplar el emparejamiento léxico superficial del razonamiento deductivo de necesidad lógica. El modelo de **7B parámetros** resolvió el 100% de los casos de negación estricta.

---

## 5. Implementación Arquitectónica Condicional (Leyes 1, 2 y 3)

Se implementó una arquitectura universal desacoplada que permite alternar entre el modelo Transformer anterior y el nuevo evaluador lineal sin romper configuraciones existentes:

### 5.1. Detección Dinámica en `llama-evaluator-srv.sh`
El script de arranque inspecciona la variable `EVALUATOR_MODEL`:
* **Si contiene `rwkv` o `finch`:** Configura alias `v6-Finch-7B-HF-Q5_K_M`, asigna contexto de 32.768 tokens, habilita los 99 layers a GPU y ejecuta un precalentamiento de kernels CUDA en subshell.
* **Si contiene `twil`:** Configura alias `twil-lm3-q4_k_m`, ventana estándar de 8.192 tokens y parámetros JSON.

### 5.2. Enrutamiento en `rag/evaluator.py`
* **Modo RWKV Lineal (`/completion`):** Emite un prompt booleano directo solicitando estrictamente `SI` o `NO` (temperatura 0.0, 4 tokens de predicción). La función mapea la respuesta al contrato DTO canónico requerido por el sistema:
  ```json
  {"suficiente": true, "motivo": "...", "faltantes": [], "evaluador": "rwkv-finch"}
  ```
* **Modo twil-lm3 (`/v1/chat/completions`):** Mantiene la llamada ChatML estructurada con esquema JSON nativo.
* **Timeout Adaptativo:** Se configuró un umbral de 6.5 segundos cuando el bloque documental supera los 15.000 caracteres, evitando fallbacks prematuros durante el prefill de grandes volúmenes.

---

## 6. Disyuntor Anti-Bucle Inter-Rondas (`gateway/core/tool_governor.py`)

### 6.1. Diagnóstico del Fallo en Chat Inicial (`chat-export-1792970822087.json`)
Antes de reiniciar el gateway tras el cambio de modelo, el proceso en memoria envió consultas ChatML al backend RWKV (que no es un modelo instruido en formato de chat). Al recibir cadenas planas, el evaluador asumió insuficiencia, provocando que el modelo generador repitiera exactamente la misma consulta vectorial durante 11 rondas hasta agotar el límite de 50.000 tokens y fugar etiquetas `<tool_call>`.

### 6.2. Causa Raíz Estructural
El gobernador de herramientas solo auditaba llamadas dentro del mensaje individual activo, pero no comprobaba si el asistente estaba repitiendo consultas idénticas ya ejecutadas en rondas anteriores del mismo turno.

### 6.3. Solución Implementada (Ley 2 y Ley 3)
Se incorporó el disyuntor anti-bucle inter-rondas:
1. Registra las firmas normalizadas (`nombre` + `argumentos`) de todas las llamadas a herramientas emitidas en rondas previas del turno.
2. Si un nuevo mensaje del asistente propone un lote compuesto exclusivamente por consultas idénticas a las ya ejecutadas, **deshabilita las herramientas de inmediato**.
3. Inyecta la directiva de corte: `[FASE DE INVESTIGACIÓN CONCLUIDA - DETECCIÓN DE BUCLE (MEA)]`, forzando al modelo a concluir con el texto disponible.

---

## 7. Validación en Producción (Auditoría de Chats Reales)

### Caso 1: Recuperación Exitosa (`chat-export-1792972341439.json`)
* **Consulta:** Jerarquía de bienes jurídicos en el ordenamiento argentino.
* **Comportamiento:** 4 llamadas progresivas (2 búsquedas vectoriales + 2 lecturas directas de Donna en *Derecho Penal Parte Especial*).
* **Consumo:** 16.979 tokens (reducción del 66% respecto a los >50k del fallo inicial).
* **Tiempo:** 35 segundos totales.
* **Resultado:** Cero bucles, dictamen doctrinal impecable sobre la vida y la integridad física.

### Caso 2: Prueba de Estrés en Obra Extensa (`chat-export-1792973088180.json`)
* **Consulta:** Análisis estructural de contratos en el ordenamiento jurídico argentino.
* **Comportamiento:** 6 herramientas ejecutadas (índice general, estructura del CCyCN, búsqueda dogmática y lectura de 3 títulos dispositivos: Contratos en general, Consumo y Contratos en particular).
* **Intervención del Gobernador:** Al alcanzar ~58.062 tokens acumulados, el `Tool Governor` aplicó el techo preventivo y deshabilitó herramientas.
* **Rendimiento de Síntesis:** El modelo Qwen 3.6 35B MoE redactó un dictamen exhaustivo de **2.604 tokens (9.433 caracteres)** a **103,12 tokens/segundo**, citando artículos precisos (957, 958, 961, 962, 1137 y concordantes del CCCN).

---

## 8. Estado Operativo del Sistema

* **Memoria GPU (RTX 3090 24GB):** 23.757 MiB asignados / 819 MiB libres. Coexistencia estable y sin OOM de:
  1. `vllm-llama.service` (Qwen 3.6 35B MoE en `:18100`)
  2. `rwkv-embeddings.service` (EmbeddingRWKV 1024D en `:18005`)
  3. `vllm-evaluator.service` (RWKV-6 Finch 7B en `:18300`)
  4. `vllm-gateway.service` (Gateway Reverse Proxy en `:8000`)
* **Almacenamiento:** Liberados ~13 GB tras purgar pesos descartados.
* **Suite de Pruebas:** 147/147 pruebas unitarias aprobadas (100% OK).
