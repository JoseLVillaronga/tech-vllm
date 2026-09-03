# 🧪 Catálogo de Pruebas de Campo: RAG Jerárquico y Alineación MEA v2.1

Este directorio almacena los registros empíricos y transcripciones de conversaciones reales ejecutadas en **vLLM Suite** con clientes como **Open-WebUI**, sirviendo como evidencia de reproducibilidad, análisis forense y verificación de invariantes.

---

## 📊 Índice de Pruebas Registradas

| Fecha | Archivo / Evidencia | Modelo | Contexto | Herramientas Invocadas | Hito Demostrado |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **2026-09-01** | [`prueba_campo_deepseek_v4_evaluacion_rag_2026-09-01.md`](prueba_campo_deepseek_v4_evaluacion_rag_2026-09-01.md) | `deepseek/deepseek-v4-flash-vision-exp` (Cloud) | ~50.8K | `buscar_en_base_de_conocimiento`<br>`obtener_estructura_documento`<br>`leer_documento_completo`<br>`buscar_en_internet` | **Evaluación crítica del RAG por modelo de frontera, diagnóstico de vigencia temporal y catálogo de 24 leyes prioritarias.** |
| **2026-09-01** | [`prueba_campo_rag_jerarquico_v2_2026-09-01.md`](prueba_campo_rag_jerarquico_v2_2026-09-01.md) | `google/gemma-4-12B-it` (Local 4-bit) | ~27.5K | `buscar_en_base_de_conocimiento`<br>`obtener_estructura_documento`<br>`leer_documento_completo` | **Flujo completo de 3 pasos (Búsqueda ➔ GPS Documental de 196 secciones ➔ Extracción quirúrgica de 5.7K tokens).** |
| **2026-09-01** | [`prueba_campo_62k_matrimonio_pdf_2026-09-01.md`](prueba_campo_62k_matrimonio_pdf_2026-09-01.md) | `google/gemma-4-12B-it` (Local 4-bit) | **62.012 tokens** | `buscar_en_base_de_conocimiento`<br>`leer_documento_completo` (59.3K tokens)<br>`generate_pdf_document` | **Digestión masiva de 59.3K tokens del Código Civil y compilación exitosa de PDF oficial de 2 páginas.** |
| **2026-09-01** | *Comparativa Local vs Cloud* | `gemma-4-12B-it` vs `gemma-4:31b-cloud` | ~13.2K | `buscar_en_base_de_conocimiento` | **Razonamiento dogmático y contextualización histórica (Ley 340 vs CCyCN de 2015).** |
| **2026-09-02** | [`prueba_campo_freno_mano_rag_y_secuencia_embudo_2026-09-02.md`](prueba_campo_freno_mano_rag_y_secuencia_embudo_2026-09-02.md) | `gemma-4-12B-it-awq` (Local) | **8.175 tokens** | `obtener_indice_biblioteca`<br>`buscar_en_base_de_conocimiento`<br>`obtener_estructura_documento`<br>`leer_documento_completo` (intercepción) | **Freno de mano RAG contra desbordamiento de contexto (de 122.8K a 8.1K tokens, -93.3%) y rigor jurídico con cero alucinación.** |

---

## 🔬 Metodología de Validación
1. **Verificación de Invariantes (Gate 1):** Cero enlaces inventados (`https://...`), 100% de ejecución de herramientas reales.
2. **Eficiencia Cognitiva:** Cero desbordes de ventana (`max_tokens` clamped en el Gateway) y recuperación precisa en menos de 70 ms.
3. **Fidelidad Documental:** Cita textual de fuentes, artículos y números de ley (Ley 340, Art. 166, 175, 206-226).
