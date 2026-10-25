# 🧪 Prueba de Campo: Atención Lineal, Ingesta Continua y Late Chunking con EmbeddingRWKV (1024D)

**Fecha:** 2026-10-25 (Sesión Tarde)  
**Entorno:** Ubuntu Linux (RTX 3090 24GB + i9-14900K 64GB)  
**Modelo de Referencia:** Qwen3-Embedding-0.6B (1024D en puerto `:18005`)  
**Modelo Evaluado:** EmbeddingRWKV-0.4B (Curriculum trained, 1024D, 24 capas, `head_size=64`)  
**Módulo Experimental:** `lab_linear_embeddings/`  
**Autor:** José Luis Villaronga  
**Agente Operativo:** Antigravity (Google DeepMind)  

---

## 1. Motivación y Causa Raíz

En las arquitecturas Transformer tradicionales (como `Qwen3-Embedding`), la sincronización nocturna masiva de documentos en LanceDB genera picos severos de asignación en tensores de activación:
$$\text{Memoria de Activación} \propto B \times L \times H \times N^2$$

Estos picos momentáneos de 3 a 5 GB provocaban contención y riesgo de `CUDA Out Of Memory` (OOM) frente al LLM principal cargado en GPU, obligando a pausar el servicio generativo durante la ingesta.

Asimismo, la fragmentación temprana clásica (*Early Chunking*) corta el texto en trozos ciegos de 512 tokens antes de pasar por el modelo, perdiendo anáforas y referencias cruzadas fundamentales en textos extensos como el Código Civil y Comercial de la Nación (CCyCN) (*"en el artículo anterior"*, *"dicho plazo legal"*).

Se planteó como hipótesis validar si un modelo basado en **Atención Lineal / SSM (EmbeddingRWKV)** permite:
1. Mantener una curva de VRAM plana sin picos de activación cuadrática.
2. Lograr paridad o superioridad en discriminación semántica e isotropía en español.
3. Habilitar **Streaming State Chunking (Late Chunking continuo)** para resolver anáforas heredando el estado recurrente $\mathcal{O}(1)$.

---

## 2. Aislamiento Modular (Ley 1 y Ley 3)

Se creó el laboratorio independiente `lab_linear_embeddings/` sin modificar ningún servicio de producción:
* **Microservicio:** `server_rwkv.py` en puerto experimental `:18055`.
* **Almacén Vectorial:** `lancedb_lab/` aislado de `data/lancedb/teccam_knowledge_base.lance`.
* **Compilación JIT:** Compilación automática de kernels CUDA (`rwkv7_state_fwd_fp16.cu`) para arquitectura `sm_86` (RTX 3090).

---

## 3. Resultados Empíricos Medidos

### 3.1. Benchmark de Rendimiento y Huella de VRAM (`bench_memory_speed.py`)

Se evaluó el prefill de secuencias en español con longitudes desde 512 hasta 32.768 tokens:

| Tokens de Entrada | Latencia (ms) | Throughput (tok/s) | VRAM Pico (MB) | Comportamiento VRAM |
| :---: | :---: | :---: | :---: | :---: |
| **512** | 314.6 ms | 1.628 t/s | 1.137,4 MB | Consumo base |
| **2.048** | 343.5 ms | 5.962 t/s | 1.185,5 MB | +48 MB |
| **4.096** | 170.1 ms | 24.077 t/s | 1.225,5 MB | +40 MB |
| **8.192** | 293.8 ms | 27.878 t/s | 1.321,5 MB | +96 MB |
| **16.384** | 586.7 ms | 27.928 t/s | 1.513,5 MB | +192 MB |
| **32.768** | 1.216,9 ms | **26.927 t/s** | **1.897,5 MB** | **+384 MB (Plano)** |

> 📌 **Hallazgo Crítico:** Procesar **32.768 tokens de corrida tomó solo 1,21 segundos** a 26.900 tokens/segundo, con un incremento de VRAM de apenas ~760 MB sobre la base. En un Transformer estándar, una matriz de atención de $32.768 \times 32.768$ desbordaría la VRAM de forma inmediata.

---

### 3.2. Evaluación A/B de Recuperación e Isotropía (`bench_retrieval.py`)

Se evaluaron 5 pares de control (CCyCN, Infoleg y soporte técnico Teccam) comparando similitudes coseno contra fragmentos positivos vs. distractores:

| ID de Prueba | Dominio | EmbeddingRWKV-0.4B (1024D) | Qwen3-Embedding-0.6B (1024D) | Veredicto |
| :--- | :--- | :---: | :---: | :---: |
| `ccycn_vicios_redhibitorios` | Jurídico | Pos: 0.5073 \| Dist: 0.3020 (**$\Delta = +0.2053$**) | Pos: 0.8409 \| Dist: 0.7857 ($\Delta = +0.0552$) | Ambos HIT (Mayor margen en RWKV) |
| `ccycn_prescripcion_danos` | Jurídico | Pos: 0.6867 \| Dist: 0.4119 (**$\Delta = +0.2748$**) | Pos: 0.8979 \| Dist: 0.7758 ($\Delta = +0.1222$) | Ambos HIT |
| `teccam_presion_hidraulica` | Técnico | Pos: 0.6049 \| Dist: 0.3112 (**$\Delta = +0.2936$**) | Pos: 0.8582 \| Dist: 0.6797 ($\Delta = +0.1785$) | Ambos HIT |
| `teccam_calibracion_sensores` | Técnico | Pos: 0.6617 \| Dist: 0.2507 (**$\Delta = +0.4110$**) | Pos: 0.8344 \| Dist: 0.6219 ($\Delta = +0.2125$) | Ambos HIT |
| `infoleg_contrataciones_pub` | Jurídico | Pos: 0.7333 \| Dist: 0.3275 (**$\Delta = +0.4059$**) | Pos: 0.8764 \| Dist: 0.7578 ($\Delta = +0.1187$) | Ambos HIT |

* **Precisión Top-1:** 5/5 (100%) para ambos modelos.
* **Isotropía y Margen Discriminativo:** En Qwen3, los distractores se agrupan en una similitud elevada (~0.62 - 0.78), reduciendo el margen medio a $+0.1374$. En EmbeddingRWKV, los distractores caen al rango ~0.25 - 0.41, ampliando el margen medio de separación a **$+0.3181$**.

---

### 3.3. Prueba de Concepto de Late Chunking en Streaming (`late_chunker.py`)

Se comparó la vectorización del Fragmento B (que contiene anáforas sin sujeto explícito: *"el incumplimiento de la carga antes mencionada en dicho plazo legal extingue toda responsabilidad"*) frente a la consulta:
*«¿Qué consecuencia produce no denunciar el vicio oculto al garante en el plazo de sesenta días?»*

* **Similitud Chunk B Aislado (Early Chunking tradicional):** `0.4444`
* **Similitud Chunk B Streamed (Heredando estado latente del Art. 1054):** `0.6428`
* **Ganancia Neta de Fidelidad Semántica:** **$+0.1984 (+44.63\%)$**

> 🎯 **Conclusión del Experimento:** El estado recurrente de RWKV preservó el sujeto ("vicio oculto", "garante", "sesenta días") e infectó positivamente la representación semántica del fragmento consecuente, eliminando la miopía de la fragmentación estática.

---

### 3.4. Evaluación Comparativa Real en LanceDB (2.967 Chunks del CCyCN)

Se indexaron los **2.967 chunks de producción** del Código Civil y Comercial de la Nación en `lab_linear_embeddings/lancedb_lab/ccycn_rwkv.lance` (vectorización completada en 52 segundos a ~11.800 tok/s).

Se ejecutó un harness de **15 consultas jurídicas complejas** (`bench_lancedb_ccycn.py`) que abarcaron Familia, Contratos, Derechos Reales, Sucesiones y Responsabilidad Civil, comparando la recuperación vectorial Top-3 contra la tabla de producción indexada con Qwen3:

| Métrica de Recuperación (15 consultas) | `Qwen3-Embedding-0.6B` (Producción) | `EmbeddingRWKV-0.4B` (Laboratorio) | Veredicto |
| :--- | :---: | :---: | :---: |
| **Precisión Top-1 (Rank 1 Exacto)** | **9/15 (60,0%)** | 8/15 (53,3%) | Paridad estadística (+1 acierto para Qwen3) |
| **Precisión Top-3 (En el Podio RAG)** | 10/15 (66,7%) | **11/15 (73,3%)** | 🏆 **RWKV recupera más contexto en el Top-3** |
| **Separación de Confianza ($\Delta_{1-2}$)** | $+0.0093$ promedio | **$+0.0261$ promedio** | 🏆 **RWKV casi triplica la nitidez entre candidatos** |

#### Casos Destacados:
* **Art. 442 (Caducidad de Compensación Económica en Divorcio):** Qwen3 falló completamente en el Top-3 (`❌`), mientras que RWKV lo ubicó en el **Puesto 1 exacto (`✔`) con similitud de 0.7456**.
* **Art. 335 (Contradocumento en Simulación de Actos Jurídicos):** Qwen3 quedó fuera del podio (`❌`), mientras que RWKV lo ubicó dentro del Top-3 (`✔`).
* **Art. 2582 (Privilegio Especial Hipotecario):** Qwen3 acertó en el Puesto 1 (`✔`), mientras que RWKV no logró priorizarlo (`❌`).

---

## 4. Estado de Cumplimiento de Principios

* **Ley 1 (Modularización):** 100% aislado en `lab_linear_embeddings/`.
* **Ley 3 (Mínimo Blast Radius):** Cero cambios en los servicios activos de producción (:18005 y LanceDB intactos).
* **Ley 4 (Integridad RAG):** Verificación empírica completa con 2.967 fragmentos reales del corpus legislativo nacional.

