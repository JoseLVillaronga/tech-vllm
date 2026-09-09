# 🧪 Prueba de Campo: Evaluación Agéntica en Deepseek Harness, Modo Agentic Bilingüe y Coronación de `gpt-oss-20b` en RAG Intensivo

* **Fecha de Ejecución:** 8 de Septiembre de 2026 (Noche)
* **Entorno de Inferencia:** `llama-server` (Llama.cpp local compilado con CUDA / MoE Offload)
* **Modelos Evaluados:**
  * **Modelo A (Sujeto Principal):** `local/gpt-oss-20b-Q4_K_M.gguf` (20B MoE local vía Gateway Puerto `:8010`)
  * **Modelo B (Referencia Comparativa):** `Qwen3.6-35B-A3B-Q4_K_M` (35B MoE local)
* **Cliente / Evaluador:** Deepseek Harness (Framework agéntico autónomo en CLI)
* **Tarea Asignada:** Desarrollo end-to-end de una aplicación web empresarial para **TECCAM S.R.L.** (Flask, Jinja2, Tailwind CDN, conexión y persistencia real en MongoDB con `.env`, navegación y formulario de contacto en puerto `5900`).
* **Evidencias Registradas:**
  * Transcripción del Harness: `temp_historial_chat/dsh-session-session-392751d2-b7d6-4283-bf42-e78d8f1c1b49.zip` (`session.jsonl`, 1.406 eventos).
  * Código generado por `gpt-oss-20b`: `/home/jose/test-web` (activo en `http://127.0.0.1:5900/`).
  * Código generado por `Qwen 35B`: `/home/jose/web-test2` (activo en `http://192.168.4.111:92/`).

---

## 🎯 1. Objetivos del Experimento

1. **Testear el Comportamiento Agéntico Autónomo de `gpt-oss-20b`:** Evaluar si el modelo puede ejecutar un ciclo completo de desarrollo de software (análisis de carpeta, inicialización de entorno, backend Flask, rutas, persistencia en MongoDB y plantillas Jinja2) bajo la orquestación de Deepseek Harness.
2. **Validar la Estabilidad Atencional en Bucles de Herramientas Extensos:** Poner a prueba la persistencia de objetivo tras decenas de comandos consecutivos de terminal, lectura y edición de archivos.
3. **Evaluar el Nuevo Modo `alignment_mode="agentic"` del Gateway (Puerto `:8010`):** Comprobar si el desacoplamiento entre directivas doctrinales (omitidas para no alterar el benchmark) y el escudo atencional en herramientas (`role: "tool"`) previene el *In-Turn Attention Decay*.
4. **Comparativa de Rendimiento y Calidad frente a `Qwen 35B`:** Contrastar tiempo de inferencia, calidad de código y diseño de interfaz entre un modelo MoE de 20B y uno de 35B.

---

## 📊 2. Comparativa Forense: `gpt-oss-20b` vs. `Qwen 35B`

| Dimensión Evaluada | `gpt-oss-20b-Q4_K_M` (Puerto 8010 Agentic) | `Qwen3.6-35B-A3B` | Análisis Técnico del Trade-Off |
| :--- | :--- | :--- | :--- |
| **Tiempo de Inferencia Total** | **~35 minutos** (13 turnos, 42 tool calls, 55 pasos) | **~210 minutos** (3 horas y media) | **`gpt-oss-20b` fue 6 veces más rápido.** Permite un flujo de trabajo ágil e interactivo; 3.5 horas resulta inviable para iteración ágil. |
| **Velocidad de Generación** | **~160 – 180 tok/s** | ~45 – 55 tok/s | El modelo 20B MoE vuela en inferencia local con un footprint de cómputo sumamente ligero. |
| **Lógica Backend y Base de Datos** | **100% Funcional y Pragmático:** `app.py` en Flask con 5 rutas, captura de POST, sanitización de campos y persistencia real en MongoDB con `pymongo`. | **Arquitectura de Gran Escala:** Creó desde cero un mini-framework PHP MVC (`Router`, `Controller`, `View`, `Database`, `schema.sql`, `.htaccess`). | Ambos lograron persistencia real en BD. Qwen sobre-ingenierizó la arquitectura; `gpt-oss-20b` fue directo a la solución solicitada. |
| **Autorrecuperación ante Errores** | **Inmediata:** Leyó los tracebacks de Jinja2 y corrigió el código en el siguiente paso. | Alta robustez, pero con costos temporales extremos por cada paso. | `gpt-oss-20b` demostró capacidad de lectura y diagnóstico certero de excepciones de Python en tiempo real. |
| **Frontend y Diseño Visual** | **Básico y Funcional:** Navbar en `bg-amber-800`, contenedores Tailwind planos, fuente Arial estándar. | **Nivel Agencia de Diseño:** Paleta corporativa extendida (`brand-50` a `brand-950`), tarjetas con sombras, degradados, transiciones suaves. | **Brecha de sensibilidad estética:** Los 20B MoE actúan como desarrolladores backend funcionales; los 35B incorporan en sus pesos mayor sofisticación gráfica. |
| **Estabilidad Atencional** | **0 Colapsos en 42 llamadas a tools.** Cero desvíos temáticos hacia sesiones anteriores gracias al recordatorio dinámico en tools. | Estable, pero con fatiga de espera para el operador. | Se confirma la eliminación definitiva del *Attention Crosstalk* en entornos agénticos. |

---

## 🔍 3. Análisis Forense de la Sesión Agéntica (`gpt-oss-20b`)

### 3.1 Hito de Backend: Integración Real con MongoDB
A diferencia de agentes que "simulan" formularios dejando acciones vacías o volcando a archivos locales, `gpt-oss-20b` leyó las credenciales de entorno `.env` (`MONGO_USER`, `MONGO_PASS`, `MONGO_HOST`, `MONGO_DB`), construyó la URI y programó el handler:
```python
@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        mensaje = request.form.get('mensaje', '').strip()
        if not all([nombre, telefono, email, mensaje]):
            flash('Todos los campos son obligatorios.', 'error')
        elif len(mensaje) > 500:
            flash('El mensaje es demasiado largo.', 'error')
        else:
            col = client[mongo_db].contactos
            col.insert_one({'nombre': nombre, 'telefono': telefono, 'email': email, 'mensaje': mensaje})
            flash('Mensaje enviado con éxito.', 'success')
            return redirect(url_for('contacto'))
    return render_template('contact.html')
```

### 3.2 Diagnóstico y Corrección Autónoma de Excepciones
Durante la sesión, el usuario ejecutó la aplicación y reportó dos errores pegando directamente los tracebacks de la consola:
1. **Turno 6:** `ValueError: too many values to unpack (expected 2)` en `get_flashed_messages()` de Jinja2.
   * *Diagnóstico del modelo:* Comprendió que en `contact.html` estaba iterando como tupla sin haber pasado `with_categories=true` en la función de Flask. Modificó el template y resolvió el error.
2. **Turno 7:** `jinja2.exceptions.TemplateNotFound: team.html`.
   * *Diagnóstico del modelo:* Identificó que la ruta `/equipo` invocaba una plantilla no creada aún; generó `templates/team.html` de inmediato.

### 3.3 El Bucle de los Turnos 10 al 13: Inercia Conversacional vs. Acción Agéntica
En los turnos 10 al 12, ante el pedido de implementar el menú hamburguesa para móviles, el modelo cayó transitoriamente en el patrón conversacional de "explicarle al usuario cómo editar el archivo" mediante diffs de Markdown en lugar de ejecutar la herramienta `edit`.
* **Causa:** En tareas puramente visuales de frontend, los modelos entrenados como chat assistants tienden a asumir que el usuario prefiere instrucciones paso a paso.
* **Resolución:** En el turno 13, ante la pregunta imperativa del usuario (*"¿Podés editarlo vos?"*), el modelo activó la herramienta `edit` y aplicó los cambios directamente en `templates/base.html`.

---

## 🏛️ 4. Mejoras Arquitectónicas Implementadas y Validadas

A raíz de los hallazgos de esta jornada, se consolidaron dos mejoras estructurales críticas en el Gateway (vLLM Suite):

### 4.1 Modo `alignment_mode="agentic"` en Puerto `:8010`
* **Desacoplamiento Estricto (Ley 1):** El puerto `:8010` elimina la inyección de invariantes doctrinales y el etiquetado del prompt del usuario para garantizar compatibilidad 100% con datasets y plantillas de evaluación (SWE-bench, Deepseek Harness).
* **Escudo Atencional Bilingüe:** Inyecta automáticamente el recordatorio de foco activo en el mensaje de la herramienta (`role: "tool"`), detectando el idioma de la tarea mediante heurística léxica:
  * **Inglés:** `📌 [ACTIVE TASK FOCUS & RELEVANCE REMINDER (ANTI-CROSSTALK)]`
  * **Español:** `📌 [RECORDATORIO DE FOCO ACTIVO Y REGLA DE PERTINENCIA (ANTI-CROSSTALK)]`
* **Protección de Contexto:** Mantiene la poda a 6 turnos de usuario y el vaciado físico de slots KV en `llama-server`.

### 4.2 Sanitización Robusta de Nombres de PDF (`sanitize_pdf_filename`)
* **Causa Raíz:** En la sesión anterior, títulos normativos como `"Decreto 1030/2020"` provocaron un error `HTTP 500 - [Errno 2] No such file or directory` porque la barra inclinada `/` fue interpretada por Linux como un subdirectorio inexistente.
* **Solución (Ley 2):** Implementada la función `sanitize_pdf_filename` en `pdf_engine.py` y `openwebui_pdf_tool.py`, neutralizando `/` y `\` como `_` (`decreto_1030_2020.pdf`) y erradicando rutas absolutas hardcodeadas en favor de rutas relativas dinámicas (`PDF_STORAGE_DIR`).

---

## 👑 5. Veredicto: `gpt-oss-20b` Destrona a `gemma-4-12b-it` en RAG Intensivo

Con la evidencia combinada de la prueba de estrés de 31 turnos de derecho positivo argentino y la evaluación agéntica de 42 pasos en Deepseek Harness, **`gpt-oss-20b` se consagra como el modelo de cabecera y estándar dorado para RAG intensivo y flujos agénticos en el cluster local**:

1. **Ingesta de Contexto Monumental:** Procesa 15.000 tokens en menos de 3 segundos (~5.000 tok/s), pulverizando la latencia de prefill de modelos densos de 12B.
2. **Capacidad Dogmática y Hermenéutica Superior:** Demostró comprensión de principios constitucionales, marco ético adaptativo (MEA v2.1) y resolución de dilemas jurídicos complejos (Art. 19 CCCN sobre la concepción biológica y el estatus de entidades artificiales).
3. **Resiliencia Operativa:** Cero colapsos de atención en sesiones de larga duración con llamadas en cadena a herramientas.
4. **Eficiencia de Recursos:** Funciona en la GPU de 24 GB dejando margen holgado de VRAM y ofreciendo generación instantánea (>160 tok/s).

**Recomendación Operativa:** Para tareas donde se requiera diseño web estético de alta gama sin supervisión, Qwen 35B sigue teniendo ventaja visual pero a un costo temporal prohibitivo. Para desarrollo funcional, RAG masivo, análisis legal y flujos interactivos, `gpt-oss-20b` es la opción indiscutida.
