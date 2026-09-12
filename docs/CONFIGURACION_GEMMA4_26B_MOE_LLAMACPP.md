# 🦙 Configuración y Despliegue de Gemma 4 26B MoE QAT en llama.cpp (Estándar Dorado)

**Proyecto:** vLLM Suite / Tech Support Argentina  
**Modelo:** `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` (`gemma-4-26B_q4_0-it.gguf`)  
**Arquitectura:** Mixture of Experts (MoE) - 26B parámetros totales, 4B parámetros activos por token  
**Cuantización:** QAT (Quantization-Aware Training) oficial de Google DeepMind en `q4_0`  
**Hardware de Destino:** GPU NVIDIA GeForce RTX 3090 (24 GB VRAM Ampere) | 64 GB RAM DDR4 | Ubuntu Linux  
**Motor de Inferencia:** `llama-server` (`llama.cpp` b3800+ con soporte CUDA y Flash Attention)  
**Fecha de Homologación:** 2026-09-12  
**Marco de Referencia:** [Modelo Ético Adaptativo (MEA v2.1 con Invariantes)](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo) y [Las Cuatro Leyes Universales](../AGENTS.md)  

---

## 🎯 1. Justificación Técnica y Estado del Arte

Tras rigurosas pruebas de campo multi-turno en entornos agénticos cerrados (*ReAct loops*), `gemma-4-26B-A4B-it-qat-q4_0` fue homologado y coronado como el **Estándar Dorado permanente** para el asistente corporativo **`CorpAI-Gen | Legal & Compliance`**.

### Ventajas Competitivas Clave:
1. **Velocidad de Generación Disruptiva:** Alcanza entre **95.0 y 108.4 tok/s** (promedio: **~103.4 tok/s**) en la RTX 3090. Esto representa un rendimiento **2.8 veces más rápido** que modelos densos equivalentes de 24B/27B.
2. **Ventana Completa de 128k Tokens en VRAM:** Gracias a la cuantización de KV Cache en `q4_0`, el contexto nominal completo de **131.072 tokens (128K)** se aloca completamente en GPU ocupando únicamente **19.1 GB de VRAM** (79.55%), dejando un margen intocable de **~4.9 GB libres** para evitar fragmentación o desbordes por CUDA OOM.
3. **Calidad Cognitiva Preservada por QAT:** A diferencia de cuantizaciones post-entrenamiento (PTQ) agresivas, el entrenamiento consciente de cuantización (QAT) de DeepMind retiene la precisión de razonamiento jurídico y dogmático de punto flotante nativo (`bfloat16`).
4. **Resiliencia Agéntica:** Supera las patologías de modelos densos previos (literalismo de docstrings, bucles de pensamiento metadiscursivo y alucinación normativa sustitutiva), resolviendo el 100% de la batería canónica de 34 turnos jurídicos.

---

## ⚙️ 2. Parámetros Óptimos de Inferencia en `.env`

Ajuste las siguientes variables en el archivo [`.env`](../.env) del proyecto (o cárguelas con un solo clic desde el Dashboard Web):

```bash
# ==============================================================================
# Inferencia Llama.cpp - Estándar Dorado: Gemma 4 26B MoE QAT (128K Ctx)
# ==============================================================================
LLAMA_DIR=$HOME/llama.cpp
LLAMA_MODEL=/models/gemma-4-26B_q4_0-it.gguf
LLAMA_ALIAS="CorpAI-Gen | Legal & Compliance"
LLAMA_PORT=18100
LLAMA_CTX_SIZE=131072
LLAMA_BATCH_SIZE=4096
LLAMA_UBATCH_SIZE=1024
LLAMA_GPU_LAYERS=999
LLAMA_N_CPU_MOE=0
LLAMA_IS_MOE=true
LLAMA_CACHE_TYPE_K=q4_0
LLAMA_CACHE_TYPE_V=q4_0
LLAMA_REASONING=off
LLAMA_LOAD_MODE=mlock
LLAMA_THREADS=8
LLAMA_PARALLEL=2
```

---

## 📋 3. Desglose y Justificación de Parámetros CLI

| Parámetro | Valor Configurado | Justificación de Ingeniería |
| :--- | :--- | :--- |
| **`--model`** | `gemma-4-26B_q4_0-it.gguf` | Archivo de pesos cuantizado oficial QAT (~14.4 GB en disco). |
| **`--ctx-size`** | `131072` | Ventana de contexto máxima de 128K tokens sin reducción preventiva. |
| **`--cache-type-k`** | `q4_0` | Cuantización de Keys en KV Cache; reduce el consumo de memoria en más del 70%. |
| **`--cache-type-v`** | `q4_0` | Cuantización de Values en KV Cache. |
| **`--gpu-layers`** | `999` | Offload del 100% de las capas a la GPU RTX 3090. |
| **`--n-cpu-moe`** | `0` | Todos los expertos se ejecutan íntegramente en los núcleos CUDA de la GPU. |
| **`--flash-attn`** | `on` | Aceleración por Flash Attention 2 (latencia mínima y reducción de buffers). |
| **`--load-mode`** | `mlock` | Bloqueo de memoria física en RAM/VRAM para impedir swapping a disco. |
| **`--reasoning`** | `off` | Desactivación de tokens de pensamiento libre (`<think>`) para forzar bucle agéntico directo. |
| **`--parallel`** | `2` | 2 slots de inferencia concurrentes para soportar peticiones paralelas. |
| **`--batch-size`** | `4096` | Lote lógico de prefill para acelerar el procesamiento de documentos RAG extensos. |
| **`--ubatch-size`** | `1024` | Micro-lote de cálculo CUDA. |
| **`--threads`** | `8` | Hilos CPU auxiliares para operaciones no matriciales. |

---

## 🖥️ 4. Configuración Rápida en el Dashboard Web

Para activar este perfil sin necesidad de editar manualmente archivos de configuración:

1. Ingrese al Dashboard Web en **`http://localhost:8004`** (o su IP autorizada).
2. Diríjase a la pestaña **Variables**.
3. Descienda hasta la sección **Inferencia Llama.cpp (MoE / Denso / Motor Local)**.
4. Haga clic en el botón destacado:  
   **`🏆 Gemma 4 26B MoE (Estándar Dorado / 128K)`**.
5. Todos los campos (`LLAMA_MODEL`, `LLAMA_CTX_SIZE`, `LLAMA_IS_MOE`, `LLAMA_CACHE_TYPE_K/V`, etc.) se completarán automáticamente con los valores validados.
6. Haga clic en **Guardar Configuración** al final del formulario.
7. Reinicie el servicio mediante el botón **`🔄 Reiniciar vllm-llama`** o desde la pestaña **Monitoreo**.

---

## 🚀 5. Operación y Verificación por Consola

### Arranque y Estado del Servicio:
```bash
# Reiniciar el servicio systemd
sudo systemctl restart vllm-llama

# Verificar estado y huella de memoria
sudo systemctl status vllm-llama

# Monitorear logs de inferencia en tiempo real
sudo journalctl -u vllm-llama -f
```

### Verificación de VRAM (NVIDIA-SMI):
```bash
nvidia-smi --query-gpu=memory.used,memory.free,temperature.gpu --format=csv
```
*Resultado Esperado:* ~19.1 GB utilizados, ~4.9 GB libres, temperatura entre 47°C y 52°C.

### Prueba de Inferencia RAG desde el Gateway (Puerto 8000):
```bash
curl -s http://localhost:8000/v1/chat/completions   -H "Content-Type: application/json"   -H "Authorization: Bearer test-key"   -d '{
    "model": "CorpAI-Gen | Legal & Compliance",
    "messages": [
      {"role": "user", "content": "¿Qué forma de gobierno adopta la Nación Argentina según el artículo 1 de la Constitución Nacional?"}
    ],
    "max_tokens": 150
  }' | jq .
```

---

## 🔒 6. Cumplimiento del Marco Ético MEA v2.1 y Leyes Universales

* **Ley 1 (Modularización Estricta):** El backend corre desacoplado en el puerto 18100, gobernado perimetralmente por el Gateway (puerto 8000), el `ContextPruner` y el `ToolGovernor`.
* **Ley 2 (Atacar Causas Raíz):** La estabilidad del contexto no se logró recortando la ventana de memoria sino optimizando la arquitectura (MoE + KV Cache Q4_0), eliminando el compromiso entre contexto y capacidad de hardware.
* **Ley 3 (Mínimo Blast Radius):** La adopción del modelo preservó intactos todos los contratos de API existentes, bases vectoriales de LanceDB y microservicios satélite de la suite.
* **Ley 4 (Integridad en Cascada RAG):** Se validó el 100% de recuperación documental gracias a la Doctrina Ontológica RAG y la ampliación a `top_k = 6`, eliminando toda alucinación inducida por contexto truncado.
* **Invariante de Portabilidad (Anti-Hardcoded Paths):** El lanzador dinámico [`llama-srv.sh`](../llama-srv.sh) resuelve dinámicamente el usuario y directorios (`$HOME/llama.cpp`), garantizando que la configuración sea 100% portable y reproducible.
