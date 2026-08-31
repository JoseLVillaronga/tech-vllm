# ❓ Preguntas Frecuentes y Guía de Resolución de Problemas (FAQ)

**Suite:** vLLM Local Suite & Open-WebUI  
**Autor y Arquitectura:** José Luis Villaronga  
**Última Actualización:** Agosto 2026

Este documento compila las preguntas más frecuentes, lecciones operativas aprendidas y soluciones canónicas a problemas recurrentes al operar la suite local vLLM con clientes como Open-WebUI o integraciones agénticas.

---

## 📑 Índice de Preguntas Frecuentes

1. [¿Por qué al generar un PDF o encadenar RAG recibo el error `Unterminated string` o JSON cortado?](#1-por-qué-al-generar-un-pdf-o-encadenar-rag-recibo-el-error-unterminated-string-o-json-cortado)
2. [¿Por qué al elegir un modelo en Open-WebUI aparece el error `Model '' was not found`?](#2-por-qué-al-elegir-un-modelo-en-open-webui-aparece-el-error-model--was-not-found)
3. [¿Por qué el chat sigue respondiendo sobre un documento PDF viejo aunque le pida cambiar de tema?](#3-por-qué-el-chat-sigue-respondiendo-sobre-un-documento-pdf-viejo-aunque-le-pida-cambiar-de-tema)
4. [¿Cómo utilizo modelos privados o no listados de proveedores como Ollama o DeepSeek?](#4-cómo-utilizo-modelos-privados-o-no-listados-de-proveedores-como-ollama-o-deepseek)
5. [¿Qué hacer si recibo `HTTP 403: Acceso denegado: IP Bloqueada en Lista Negra`?](#5-qué-hacer-si-recibo-http-403-acceso-denegado-ip-bloqueada-en-lista-negra)
6. [¿Cómo pruebo rápidamente la Diarización de Voz (PyAnnote 3.1) desde la consola?](#6-cómo-pruebo-rápidamente-la-diarización-de-voz-pyannote-31-desde-la-consola)
7. [¿Cómo decide la suite si inyectar un documento completo oficial o hacer búsqueda por fragmentos (chunks)?](#7-cómo-decide-la-suite-si-inyectar-un-documento-completo-oficial-o-hacer-búsqueda-por-fragmentos-chunks)
8. [¿Qué son las Tres Leyes de Villaronga y el Modelo Ético Adaptativo (MEA v2.1)?](#8-qué-son-las-tres-leyes-de-villaronga-y-el-modelo-ético-adaptativo-mea-v21)
9. [¿Por qué un modelo como Gemma 4 12B alucina o falla al usar herramientas y cómo solucionarlo con 8 bits?](#9-por-qué-un-modelo-como-gemma-4-12b-alucina-o-falla-al-usar-herramientas-y-cómo-solucionarlo-con-8-bits)

---

### 1. ¿Por qué al generar un PDF o encadenar RAG recibo el error `Unterminated string` o JSON cortado?

* **Causa Raíz:** La **Doble Ventana de Tokens** en Open-WebUI. La configuración general (*Context Length: 65.000 tokens*) gobierna únicamente la ventana de **Entrada (*Input*)**. La ventana de **Salida (*Output / Completion Budget*)** se controla independientemente desde el panel lateral de **Controles del Chat (`max_tokens`)**, que por defecto viene limitado a **2.048 tokens**. Al emitir un documento extenso dentro del JSON de la herramienta, el modelo corta la respuesta al token 2.014 antes de cerrar la llave del JSON.
* **Solución:**
  1. En la ventana del chat de Open-WebUI, abrí el panel lateral derecho **Controles (⚙️)**.
  2. Buscá el deslizador **`max_tokens`** y subilo a **`16384`** o **`65536`**.

---

### 2. ¿Por qué al elegir un modelo en Open-WebUI aparece el error `Model '' was not found`?

* **Causa Raíz:** En Open-WebUI existe un preset personalizado bajo **Espacio de Trabajo (Workspace) ➔ Modelos** cuyo campo obligatorio **"Modelo Base" (Base Model)** quedó **vacío (`""`)**. Al chatear, Open-WebUI intenta despachar la petición al modelo base `""` y aborta antes de consultar a nuestro Gateway.
* **Solución:**
  * **Opción A (Recomendada):** Andá a **Espacio de Trabajo ➔ Modelos** y eliminá (🗑️) ese preset duplicado. Open-WebUI tomará directamente el modelo nativo expuesto por el Gateway.
  * **Opción B:** Editá el preset y seleccioná el modelo base correspondiente en el menú desplegable.
  * Luego, andá a **Ajustes ➔ Conexiones** y hacé clic en **Verificar / Guardar 🔄**.

---

### 3. ¿Por qué el chat sigue respondiendo sobre un documento PDF viejo aunque le pida cambiar de tema?

* **Causa Raíz:** **Contaminación de Memoria en el Hilo de Chat.** Cuando subís un archivo adjunto directamente a un chat en Open-WebUI, el cliente re-inyecta el texto completo del archivo (~8.000+ tokens) en **cada mensaje subsecuente** de esa conversación.
* **Solución:** Cuando termines de consultar un documento adjunto temporal y quieras investigar en la base documental permanente (RAG LanceDB) o cambiar de tema, **iniciá siempre un chat nuevo y limpio**.

---

### 4. ¿Cómo utilizo modelos privados o no listados de proveedores como Ollama o DeepSeek?

* **Causa Raíz:** Algunos proveedores devuelven una lista reducida en su endpoint `/v1/models`, ocultando modelos especializados o privados.
* **Solución:**
  1. Abrí el Dashboard Web (`:8004` o `:18004`) en la pestaña **Seguridad ➔ Claves API**.
  2. Editá tu clave API y desplegá el proveedor en la nube (ej. `☁️ Ollama`).
  3. En el campo inferior `[ ID de modelo manual / no listado ]`, escribí el identificador exacto (ej: `gemma4:31b`, `deepseek-r1:latest`) y hacé clic en **`➕ Agregar`**.
  4. Guardá la clave. El modelo quedará persistido como `✨ (Manual)` y aparecerá automáticamente en el listado de Open-WebUI (`GET /v1/models`).

---

### 5. ¿Qué hacer si recibo `HTTP 403: Acceso denegado: IP Bloqueada en Lista Negra`?

* **Causa Raíz:** El filtro de seguridad Fail2ban del Gateway bloqueó automáticamente tu IP tras múltiples intentos con credenciales erróneas o peticiones malformadas.
* **Solución:**
  * Desde el Dashboard Web: Andá a **Seguridad ➔ Reglas de IP / Lista Negra** y eliminá el registro de bloqueo.
  * Por consola (MongoDB):
    ```bash
    python -c "from config import get_mongo_uri, MONGO_DB; from pymongo import MongoClient; db = MongoClient(get_mongo_uri())[MONGO_DB]; db.ip_rules.delete_many({'action': 'blacklist'}); print('Bloqueos eliminados')"
    ```

---

### 6. ¿Cómo pruebo rápidamente la Diarización de Voz (PyAnnote 3.1) desde la consola?

* **Solución:** Ejecutá el script de prueba rápida por CLI que lee la `API_KEY` de forma segura desde `.env`:
  ```bash
  # Prueba con el audio de diálogo oficial de 2 hablantes:
  python tests/run_diarization_test.py

  # O prueba con cualquier archivo de audio propio:
  python tests/run_diarization_test.py ruta/a/mi_grabacion.wav
  ```

---

### 7. ¿Cómo decide la suite si inyectar un documento completo oficial o hacer búsqueda por fragmentos (chunks)?

* **Mecanismo:** El Gateway utiliza un algoritmo de resolución jerárquico inteligente (`proxy_factory.py`):
  1. Analiza si la consulta menciona un documento específico de la biblioteca (ej: *Constitución Nacional*, *Procedimiento de Soporte Teccam*).
  2. Si el documento tiene **$\le 30.000$ tokens**, inyecta el **100% del documento oficial íntegro (Fidelidad 100%)**, eliminando cualquier pérdida por partición en chunks.
  3. Si el documento es gigantesco (ej. *Código Civil*), ejecuta búsqueda focalizada con `top_k=8` restringida al tema de ese documento.
  4. Para preguntas abiertas, ejecuta búsqueda vectorial híbrida con `top_k=8`.

---

### 8. ¿Qué son las Tres Leyes de Villaronga y el Modelo Ético Adaptativo (MEA v2.1)?

* **Leyes de Ingeniería ([`AGENTS.md`](file:///home/jose/vllm/AGENTS.md)):**
  1. **Ley 1:** Modularización estricta y separación de responsabilidades desde el día cero.
  2. **Ley 2:** Atacar causas raíz cuando el riesgo de fallo en cadena es bajo.
  3. **Ley 3:** Principio del mínimo cambio posible (*Navaja de Ockham / Mínimo Blast Radius*).
* **Modelo Ético Adaptativo ([`docs/MEA_AI_ALIGNMENT.md`](file:///home/jose/vllm/docs/MEA_AI_ALIGNMENT.md)):**  
  Estructura de optimización con restricciones ($\max \text{Valores}$ sujeto a $\text{Invariantes} = \text{True}$) con cálculo formal de RVI y deber de objeción ante daño potencial. Repositorio teórico: [Modelo-Etico-Adaptativo](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo).

---

### 9. ¿Por qué un modelo como Gemma 4 12B alucina o falla al usar herramientas y cómo solucionarlo con 8 bits?

* **Causa Raíz:** La cuantización de 4 bits (`bitsandbytes` NF4) es excesivamente agresiva para modelos densos de ~12B parámetros. Comprimir los pesos a solo 16 niveles discretos colapsa los *outliers* de activación en las capas de atención responsables del parsing JSON, la delimitación de argumentos y la memoria a corto plazo, provocando pérdida de contexto, alucinaciones y llamadas rotas en cadenas multi-herramienta.
* **Solución:** Activar la cuantización de **8 bits (`LLM.int8()`)**, que conserva los 256 niveles de precisión y aísla los vectores *outliers* en 16 bits sin disparar el consumo de VRAM.
  1. En tu archivo `.env`, configurá:
     ```env
     LOAD_8_BITS=true
     ```
  2. Reiniciá el servicio del motor (`vllm-app.service` o `sudo systemctl restart vllm-app.service`).
  3. El modelo recuperará inmediatamente la fidelidad deductiva, el seguimiento estricto de esquemas de herramientas y la memoria de contexto.

