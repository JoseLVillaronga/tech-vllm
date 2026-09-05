# 🏆 Perfil Canónico de Producción: Gemma 4 12B IT para Entornos de Oficina con RAG Intensivo

**Proyecto:** vLLM Local Suite / Tech Support Argentina  
**Autor y Supervisor:** José Luis Villaronga  
**Fecha:** 5 de septiembre de 2026  
**Hardware de Referencia:**  
* **GPU:** NVIDIA GeForce RTX 3090 (24 GB VRAM GDDR6X, Ampere)  
* **RAM:** 64 GB DDR4  
* **CPU:** 8 núcleos / 16 hilos  
* **Almacenamiento:** NVMe PCIe 4.0  
* **Sistema Operativo:** Ubuntu Linux (Kernel x86_64)

---

## 🎯 1. Dictamen Técnico y Declaración de Estándar Dorado

Tras exhaustivas pruebas empíricas en campo comparando arquitecturas densas, híbridas (MoE) y de frontera (Qwen 3.6 35B MoE, Llama 3.3 70B y Gemma 4), se establece que **Gemma 4 12B IT (Q4_K_M) sobre el motor nativo `llama.cpp`** es la **mejor opción global de producción** para tareas de oficina profesional (jurídico, administrativo, contractual y normativo) con perfil de **RAG intensivo**.

---

## ⚙️ 2. Parámetros Óptimos de Calibración (`.env` y `llama-srv.sh`)

| Variable | Valor Calibrado | Justificación Técnica |
| :--- | :---: | :--- |
| **`LLAMA_MODEL`** | `$LLAMA_DIR/models/gemma-4-12B-it-Q4_K_M.gguf` | Cuantización simétrica balanceada; preserva fidelidad sintáctica y relacional. |
| **`LLAMA_ALIAS`** | `gemma-4-12B-it-Q4_K_M` | Identificador expuesto en OpenAI API (`/v1/models`). |
| **`LLAMA_PORT`** | `18100` | Puerto interno seguro detrás del Gateway (`8000`). |
| **`LLAMA_CTX_SIZE`** | `131072` (131K tokens) | Buffer masivo que cubre leyes completas, códigos o expedientes extensos. |
| **`LLAMA_BATCH_SIZE`** | `4096` | Throughput de ingesta masiva en la cola de planificación. |
| **`LLAMA_UBATCH_SIZE`** | `1024` | Micro-batch físico que acota activaciones en GPU, blindando contra OOM en 131k. |
| **`LLAMA_GPU_LAYERS`** | `999` (100% VRAM) | Descarga total del modelo denso en la RTX 3090. Cero latencia de bus PCIe/RAM. |
| **`LLAMA_N_CPU_MOE`** | `0` | Modelo denso: sin expertos en CPU RAM. |
| **`LLAMA_REASONING`** | `off` | Modo texto directo sin bloques `<think>`. Elimina la simulación mental y fuerza tool-calls. |
| **`LLAMA_LOAD_MODE`** | `mlock` | Bloqueo estricto en RAM/VRAM con `LimitMEMLOCK=infinity` (cero swapping del kernel). |
| **`LLAMA_THREADS`** | `8` | Hilos de cómputo dedicados. |
| **`LLAMA_PARALLEL`** | `1` (FIFO dinámico) | Garantiza el 100% de los 131.072 tokens indivisos por consulta, sin riesgo de truncamiento. |

---

## 📊 3. Métricas de Rendimiento en Producción (RTX 3090 24GB + 64GB RAM)

| Métrica de Rendimiento | Valor Medido en Caliente | Impacto Operativo en Oficina |
| :--- | :---: | :--- |
| **Ocupación de VRAM (Estable)** | **17.7 GB / 24.0 GB (73.7%)** | Residencia total en memoria GDDR6X ultrarrápida. |
| **Margen de Seguridad de VRAM** | **6.3 GB libres** | Permite convivir con `vllm-embeddings` (Qwen3-Embedding en CUDA: ~1.1 GB) sin riesgo de colisión. |
| **Velocidad de Prefill (Ingesta)** | **~2.300 a 2.480 tokens/segundo** | Ingiere chunks RAG de 2.000 a 4.000 tokens en menos de 150 milisegundos. |
| **Velocidad de Generación** | **62.0 a 63.8 tokens/segundo** | Respuestas de 300 tokens se imprimen en 4.5 segundos (~4x la velocidad de lectura humana). |
| **Latencia entre Ciclos (Prefill)** | **Sub-milisegundo (< 1 ms)** | Cero "burbujas de GPU" gracias a la implementación nativa en C++ de `llama.cpp`. |
| **Concurrencia Operativa** | **Oficina de 5 personas** | Tiempos de espera imperceptibles (2 a 3 segundos en colisiones estadísticas). |
| **Perfil Térmico** | **48°C a 62°C** | La GPU descansa entre consultas mientras el usuario lee; cero estrangulamiento térmico. |

---

## 🔬 4. Cuadro Comparativo: Gemma 4 12B vs. Alternativas

| Dimensión de Análisis | Gemma 4 12B IT (Denso) | Qwen 3.6 35B MoE (A3B) | Modelos 70B (Llama 3.3 / Q4) |
| :--- | :---: | :---: | :---: |
| **Alojamiento en RTX 3090** | **100% en VRAM (17.7 GB)** | Híbrido (VRAM + 18 capas en RAM) | Híbrido forzado (~40 capas en RAM) |
| **Velocidad de Prefill (RAG)** | 🚀 **~2.350 t/s** (Instantáneo) | ⚡ ~650 t/s | 🐢 ~180-250 t/s |
| **Velocidad de Generación** | 🚀 **~63 t/s** | ⚡ ~48 t/s | 🐢 ~12-18 t/s |
| **Ventana de Contexto Útil** | **131.072 tokens nativos** | 131.072 tokens | Limitado a 16K-32K por falta de RAM/VRAM |
| **Docilidad Agéntica (Tools)** | ⭐⭐⭐⭐⭐ Impecable | ⭐⭐⭐⭐ Requiere `--reasoning off` | ⭐⭐⭐ Lento para bucles ReAct |
| **Costo Energético / Térmico** | Muy Bajo (Duty cycle 15-20%) | Moderado | Alto (CPU y GPU al 100% continuo) |

---

## 🛡️ 5. Blindaje Ético y Operativo (Integración MEA v2.1)

1. **Invariante 5 de Grounding Activo:**  
   Al desactivar el razonamiento libre (`--reasoning off`), Gemma 4 canaliza su capacidad cognitiva en emitir llamadas directas a `buscar_en_base_de_conocimiento` y `leer_documento_completo`.
2. **Cero Simulación Mental:**  
   No malgasta tokens narrando su proceso interno (`[En proceso...]`), sino que ejecuta la herramienta técnica en 80-95 ms.
3. **Fidelidad Documental:**  
   En pruebas con la Constitución Nacional y el Código Civil y Comercial, alcanzó **100% de exactitud literal** citando artículos y reconociendo normas vigentes y derogadas.
