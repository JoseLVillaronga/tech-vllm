# 🧪 Prueba de Campo: Inferencia Agéntica de Qwen 3.6 35B MoE con Llama.cpp y Compilación PDF

**Fecha de Ejecución:** 3 de septiembre de 2026  
**Modelo Evaluado:** `Qwen3.6-35B-A3B-Q4_K_M.gguf` (35B parámetros totales, 3B activos)  
**Motor de Inferencia:** `llama-server` (compilado localmente desde [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp))  
**Infraestructura:** NVIDIA GeForce RTX 3090 (24 GB VRAM Ampere) | 64 GB RAM DDR4 | Ubuntu Linux  
**Supervisión y Arquitectura:** José Luis Villaronga  
**Documento Generado:** `analisis_modelo_etico_adaptativo_v2.pdf` (4 páginas, 10.1 KB)

---

## 🎯 1. Objetivo de la Prueba

Evaluar el rendimiento, la capacidad agéntica de encadenamiento de herramientas (*tool-calling*) y la precisión dogmática de un modelo de frontera MoE (Mixture of Experts) de 35 mil millones de parámetros corriendo 100% en local mediante `llama-server`.

La prueba consistió en:
1. Localizar y diferenciar las versiones del **Modelo Ético Adaptativo** (v1 vs v2.1) en LanceDB mediante `buscar_en_base_de_conocimiento` y `obtener_indice_biblioteca`.
2. Navegar el árbol de 48 secciones del documento vigente mediante el **GPS Documental** (`obtener_estructura_documento`).
3. Ejecutar lecturas quirúrgicas secuenciales (`leer_documento_completo`) para extraer los 9 Valores Universales, sus Invariantes asociados, el *ius cogens*, el escalamiento por excepción y el mecanismo de invalidación.
4. Compilar un informe ejecutivo oficial de 4 páginas mediante la herramienta interna `generate_pdf_document`.

---

## ⚡ 2. Métricas de Rendimiento en Consola

Durante las 15 llamadas agénticas consecutivas, la consola de `llama-server` arrojó las siguientes métricas:

```text
Prompt Processing Speed:  650.0 – 675.0 tokens/segundo sostenidos
Generation Speed (tg):    47.5 – 53.5 tokens/segundo (~20 ms/token)
Máximo Contexto Evaluado: 20.582 tokens acumulados en 30.6 segundos
Reutilización de Grafos:  7.070 grafos de cómputo reciclados (LCP Prefix Caching)
VRAM Total Ocupada:       21.8 GB / 24.0 GB (90.8%)
```

---

## 🔄 3. Coreografía de Herramientas Registrada (Transcripción JSON)

1. **Consulta Inicial:** El usuario solicita buscar el "modelo ético adaptativo".
2. **Detección de Recencia:** El modelo recupera la v1 (`67b376f2...`), identifica el estado **`[PARCIALMENTE VIGENTE]`** y advierte formalmente sobre posibles reformas.
3. **Desambiguación:** Ante la consulta por la versión vigente, consulta el índice ontológico (`obtener_indice_biblioteca`), localiza el **`Modelo Etico Adaptativo v2 [VIGENTE]`** (`6a927cbc...`) y solicita su GPS.
4. **15 Lecturas Quirúrgicas en Cadena:**
   - Sección `0. Resumen de cambios (v1 → v2.1)`
   - Sección `3. Los 9 Valores Universales y sus Invariantes Asociados`
   - Secciones individuales de los valores 1 al 9 (`Bienestar colectivo`, `Transparencia`, etc.)
   - Sección `Meta-invariante transversal`
   - Sección `4. Invariantes Universales Mínimos (Piso Absoluto)`
   - Sección `2.4 Formulación general: Optimización ética con restricciones`
   - Sección `7.2 Escalamiento por excepción`
   - Sección `7.3 Mecanismo de invalidación`
5. **Generación de PDF Oficial:**
   - Invocación de `generate_pdf_document` enviando el análisis estructurado en Markdown.
   - Compilación en `pdf_engine.py` de un documento de 4 páginas con tablas de 5 columnas, cabeceras estilizadas, viñetas tipográficas y paginación institucional.

---

## 🏆 4. Conclusiones y Créditos Técnicos

1. **Eficacia del Modelo MoE con Llama.cpp:** Qwen 3.6 35B MoE demostró una velocidad de generación de ~50 t/s, más del doble que modelos densos equivalentes en FP16, manteniendo una fidelidad contextual insuperable.
2. **Cero Alucinación:** El modelo no inventó datos, citó textualmente la formulación de la obra de José Luis Villaronga y respetó de forma milimétrica el contrato ontológico del RAG.
3. **Agradecimiento Institucional:** Este hito operativo fue posible gracias al motor de inferencia de alto rendimiento desarrollado por el equipo de **[llama.cpp](https://github.com/ggml-org/llama.cpp)** (liderado por Georgi Gerganov), cuya compilación nativa en C++/CUDA representa el estándar de oro en eficiencia para hardware local.
