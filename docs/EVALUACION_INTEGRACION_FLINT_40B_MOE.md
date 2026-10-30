# 🦙 Evaluación e Integración Técnica: Flint Preview 40B MoE en vLLM Suite

**Proyecto:** vLLM Suite / Tech Support Argentina  
**Autor y Supervisor:** José Luis Villaronga  
**Fecha:** 30 de octubre de 2026  
**Entorno de Hardware:** NVIDIA GeForce RTX 3090 (24 GB VRAM Ampere) | 64 GB RAM DDR4 | Ubuntu Linux  
**Motor de Inferencia:** `llama.cpp` upstream (`v0.8.0-dev build 12016 commit 792fcf4e7`)  
**Modelo Evaluado:** `flint-UD-Q2_K_XL.gguf` (Unsloth Dynamic Quants, ~13 GB)

---

## 🏛️ 1. Identificación y Arquitectura del Modelo

**Flint Preview** es un modelo de lenguaje de arquitectura **Mixture of Experts (MoE) de grano fino** con un volumen total de **40 mil millones de parámetros (40B)**. Representa el modelo de mayor envergadura total desplegado en la suite hasta la fecha.

### Topología y Parámetros Estructurales (Metadatos GGUF):
* **Parámetros Totales:** ~40B.
* **Bloques / Capas Totales (`block_count`):** 49 bloques.
* **Capas Densas Iniciales (`leading_dense_block_count`):** 2 capas.
* **Total de Expertos (`expert_count`):** 256 expertos enrutados.
* **Expertos Activos por Token (`expert_used_count`):** 6 expertos.
* **Expertos Compartidos (`expert_shared_count`):** 2 expertos transversales (`shared_feed_forward_length = 1024`).
* **Mecanismo de Atención:** Grouped-Query Attention (GQA) 8:1 (32 attention heads, 4 KV heads).
* **Formato y Cuantización:** GGUF v3 con matriz de importancia dinámica Unsloth (`Q2_K_XL`, ~13 GB de peso en disco).

---

## 🔬 2. Diagnóstico de Incompatibilidad Inicial y Solución de Causa Raíz (Ley 2)

### A. Diagnóstico del Fallo de Inicialización
* **Síntoma:** El modelo levantaba correctamente en entornos externos como LM Studio, pero fallaba en la suite arrojando error de arquitectura desconocida:
  ```text
  llama_model_load: error loading model: unknown model architecture: 'flint'
  llama_init_from_model: failed to load model
  ```
* **Causa Raíz Estructural:** La arquitectura `flint` es una adición muy reciente a la especificación GGUF, implementada en upstream `llama.cpp` mediante el PR #30928 (`src/models/flint.cpp`). El binario compilado en `$USER_HOME/llamAmpere` correspondía a una versión previa optimizada para kernels de Qwen MoE que aún no incluía el parser ni los operadores de grafo para Flint.

### B. Solución Quirúrgica y Enrutamiento Dinámico (Ley 1 y Ley 3)
1. **Actualización del Motor Upstream:** Se descargó y compiló la rama `master` más reciente de `llama.cpp` en `$USER_HOME/llama.cpp` (`build 12016`), habilitando soporte nativo para `flint.cpp` con aceleración CUDA completa.
2. **Auto-Enrutamiento Determinista en `llama-srv.sh`:** En lugar de bifurcar la configuración de servicios, se incorporó una regla condicional en el lanzador que detecta la familia del modelo:
   * Si el modelo contiene la cadena `flint`, selecciona automáticamente el binario `$USER_HOME/llama.cpp/build/bin/llama-server`.
   * Para los demás modelos, preserva la ruta configurada en `$LLAMA_BIN` o `$LLAMA_DIR`.

---

## ⚡ 3. Benchmarks de Rendimiento: Flint 40B MoE vs. Qwen 3.6 35B MoE

Las pruebas de estrés se realizaron en la RTX 3090 monolítica con una ventana de contexto de **131.072 tokens** y 2 slots paralelos (`--parallel 2`):

| Métrica de Inferencia | Qwen 3.6 35B MoE (A3B) | Flint Preview 40B MoE (6+2/256) | Análisis Comparativo |
|---|---|---|---|
| **Topología MoE** | 64 expertos / 8 activos (~3B activos) | 256 expertos / 6 activos + 2 comp. | Grano más fino en Flint |
| **Velocidad Decode (Generación libre)** | **105 - 140+ tok/s** 🏆 | **75 - 80 tok/s** | Qwen mantiene el liderazgo en velocidad bruta |
| **Decode Profundo (52K tokens en contexto)** | ~85 - 95 tok/s | **57 - 58 tok/s** | Sólida estabilidad en Flint |
| **Prefill Corto (~8.5K tokens)** | ~3.200 - 3.500 tok/s | **2.880 - 3.144 tok/s** | Procesamiento por lotes eficiente en ambos |
| **Prefill Masivo (~52K tokens acumulados)** | ~2.600 tok/s | **2.400 - 2.440 tok/s** | Apenas ~20% de decaimiento en contexto ultra-largo |

> **Evaluación de Rendimiento:** Aunque Qwen 3.6 35B conserva el campeonato en velocidad de generación pura gracias a sus kernels altamente optimizados, Flint 40B ofrece una tasa sostenida de **~58 tokens/segundo con 52.000 tokens cargados en VRAM**, lo que garantiza una fluidez interactiva óptima en flujos RAG pesados.

---

## 💾 4. Evaluación de Cuantización de KV-Cache: Simétrica vs. Asimétrica

Se evaluaron dos sesiones idénticas de consulta doctrinaria profunda de 3 turnos, contrastando los dos esquemas de cuantización de memoria de atención:

### Resumen de Pruebas de Campo:

| Dimensión Evaluada | Chat 1: Simétrica (`K=q4_0 / V=q4_0`) | Chat 2: Asimétrica (`K=q8_0 / V=q4_0`) |
|---|---|---|
| **Archivo de Exportación** | `chat-export-1793389784406.json` | `chat-export-1793390228964.json` |
| **Throughput Prefill (52K tokens)** | 2.400,8 tok/s (0.416 ms/tok) | **2.403,8 tok/s** (0.416 ms/tok) |
| **Throughput Decode (52K tokens)** | **58,11 tok/s** (17.21 ms/tok) | **57,12 tok/s** (17.51 ms/tok) |
| **Reutilización de Cache (LCP)** | 0 tokens (en rama final) | **11.776 tokens cacheados** |
| **Tokens Totales Procesados** | 257.082 tokens | **397.534 tokens** |
| **Herramientas Ejecutadas** | 12 llamadas (índice + búsqueda) | **13 llamadas** (+ GPS y lectura focalizada) |

### Hallazgos de Calidad de Atención y Direccionamiento (Keys Q8 vs Q4):
1. **Conservación de Throughput:** Pasar las *Keys* a `q8_0` manteniendo los *Values* en `q4_0` tuvo una penalización de generación de apenas **1.7%** (de 58.11 a 57.12 tok/s), imperceptible para el usuario.
2. **Capacidad de Navegación Ontológica:** Bajo `K=q8_0`, el modelo demostró mayor autonomía para encadenar herramientas complementarias: utilizó `obtener_estructura_documento` para mapear el índice del *Manual de la Constitución Reformada* e intentó lecturas selectivas mediante `leer_documento_completo`.
3. **Resolución Dogmática y Exactitud de Citas:**
   * Con `q4_0 / q4_0`, el modelo identificó la *Dignidad de la persona humana* citando fuentes generales (art. 51 CCCN, art. 19 CN, Zaffaroni).
   * Con `q8_0 / q4_0`, el modelo alcanzó un estándar de máxima fidelidad documental: identificó que el bien jurídico central más protegido es el **bien personalísimo de la persona humana / derecho a la vida**, citando con rigor las posturas de *Bidart Campos*, *Carlos Creus* y los fallos de la Corte Suprema (*Kot 1958*, *Bahamóndez 1993*, *Simón 2005*).

---

## 🏛️ 5. Cumplimiento del Marco Ético MEA y Reglas de Desarrollo

1. **Protocolo Agéntico (Zero-Preamble):** Cumplimiento al 100%. Flint emite directamente el bloque de pensamiento y la llamada a función sin emitir texto conversacional previo.
2. **Invariante de Veracidad:** Cero alucinaciones detectadas. Todas las obras, autores y artículos citados corresponden a fragmentos recuperados de LanceDB.
3. **Regla de Cierre de Contexto:** Al superar los 50.000 tokens acumulados por llamadas sucesivas a herramientas, el razonamiento interno de Flint detectó autónomamente el límite y procedió a la síntesis conclusiva sin caer en bucles de reintento.
4. **Economía Verbal (Ley 5 / ASD-STE100):** Las respuestas estructuradas omitieron preámbulos ceremoniales y fórmulas de cierre comercial.

---

## 📋 6. Conclusiones y Recomendación de Producción

1. **Estabilidad del Modelo:** Flint 40B MoE es un modelo robusto para tareas de análisis documental exhaustivo y razonamiento jurídico complejo.
2. **Configuración Óptima de KV-Cache:** Se recomienda estandarizar **`--cache-type-k q8_0 --cache-type-v q4_0`**. Esta configuración asimétrica proporciona la fidelidad de atención y direccionamiento de un buffer de 8 bits para las llaves, minimizando la degradación en contextos de 50K+ tokens sin incurrir en el costo de memoria ni de velocidad de un esquema `q8/q8`.
3. **Coexistencia en la Suite:** La suite mantiene plena interoperabilidad: Qwen 3.6 35B para escenarios de máxima velocidad y volumen de consultas estándar, y Flint 40B para tareas de investigación profunda donde se requiera contrastar análisis de alta dimensionalidad.
