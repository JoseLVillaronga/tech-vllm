# 🧪 Laboratorio de Embeddings Lineales y State-Centric Retrieval (RWKV-7 / Mamba)

## Propósito
Banco de pruebas aislado para investigar, validar y comparar arquitecturas de atención lineal y modelos de estado recurrente (SSM / RWKV) aplicados a:
1. Ingesta masiva sin picos de VRAM de activación $\mathcal{O}(N^2)$.
2. Evaluación de fidelidad semántica e isotropía en idioma español frente a `Qwen3-Embedding-0.6B`.
3. Prototipado de **Late Chunking en streaming** sobre contextos extensos (ej. Código Civil y Comercial de la Nación).

## Principios de Ingeniería
* **Ley 1 (Modularización):** Aislamiento total del entorno de producción.
* **Ley 3 (Mínimo Blast Radius):** Cero impacto sobre los microservicios activos (:18005, :18000, :18100) ni sobre las tablas reales de LanceDB.
* **Ley 4 (Integridad en Cascada RAG):** Cero transiciones a producción sin validación empírica en español (MTEB/Ground-Truth).
* **Ley 5 (ASD-STE100):** Estructura clara, scripts directos y reproducibles.

## Estructura del Directorio
* `models/`: Archivos de pesos descargados (`.pth`, `.safetensors`).
* `data/`: Datasets de prueba jurídicos y técnicos en español.
* `lancedb_lab/`: Base de datos vectorial efímera e independiente para pruebas A/B.
* `download_model.py`: Script para descargar checkpoints desde Hugging Face (`howard-hou/EmbeddingRWKV`).
* `server_rwkv.py`: Servidor FastAPI experimental en puerto `:18055` (API compatible con OpenAI).
* `bench_memory_speed.py`: Medición de VRAM y tokens/segundo en prefill de secuencias largas.
* `bench_retrieval.py`: Comparativa A/B de similitud semántica y discriminación contra `Qwen3-Embedding-0.6B`.
* `late_chunker.py`: Pipeline experimental de prefill de contexto amplio y extracción de spans.

## Guía de Inicio Rápido
1. Descargar el modelo base (~389M):
   ```bash
   python download_model.py --model base
   ```
2. Ejecutar prueba de rendimiento y memoria:
   ```bash
   python bench_memory_speed.py
   ```
3. Ejecutar comparación de recuperación contra producción:
   ```bash
   python bench_retrieval.py
   ```
