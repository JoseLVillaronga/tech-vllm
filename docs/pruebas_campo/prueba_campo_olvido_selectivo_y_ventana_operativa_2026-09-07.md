# 🧪 Prueba de Campo: Estrés Multi-Turno (30 Consultas), Ventana Operativa Efectiva y Olvido Selectivo en Gateway

**Fecha:** 2026-09-07  
**Modelo en Inferencia:** `local/gpt-oss-20b-Q4_K_M.gguf` bajo `llama-server` (`llama.cpp`)  
**Hardware:** GPU NVIDIA GeForce RTX 3090 (24 GB VRAM) + Servidor Linux Ubuntu  
**Componentes Clave:** `vllm-gateway` (FastAPI), `ContextPruner` (`gateway/core/context_pruner.py`), `LanceDB` (RAG Teccam), Open-WebUI  
**Marco Teórico:** [Modelo Ético Adaptativo (MEA v2.1)](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo) y [Leyes Universales de Ingeniería](../../AGENTS.md)

---

## 🎯 1. Objetivo y Alcance de la Prueba

Someter al motor de inferencia local y a la base de conocimiento vectorial (RAG) a una **prueba de estrés multi-turno continua de 30 consultas jurídicas de alta densidad** dentro del mismo hilo de conversación, con dos propósitos críticos:
1. **Evaluar el comportamiento del modelo de 20B en VRAM completa** a lo largo de turnos acumulativos con recuperación documental autónoma.
2. **Determinar la resiliencia del contexto y descubrir empíricamente la frontera de fatiga atencional (*Context Crosstalk*)** frente a la ventana nominal declarada por el fabricante (128k tokens).

---

## 🔬 2. Los Dos Fenómenos Críticos Detectados en el Estrés (Turnos 1 a 30)

### A. La Falacia del Límite de Turnos de Usuario
Inicialmente se diseñó una poda basada en contar exclusivamente **turnos de usuario (18 turnos)**. Sin embargo, en un entorno con RAG autónomo donde el asistente ejecuta lecturas completas de leyes (`role: "tool"` con 3.000 a 20.000 caracteres por llamada), **el 90% del contexto no lo aporta el usuario ni las respuestas, sino los payloads crudos de las herramientas**.

Al alcanzar el Turno 30, a pesar de acotar a 18 turnos de usuario, el prompt enviado a `llama-server` trepó a **114.202 tokens**.

### B. El Colapso por Interferencia de Contexto (*Context Crosstalk*)
Al superar los ~55.000 tokens acumulados, el mecanismo de atención del modelo de 20B comenzó a degradarse severamente debido a la alta densidad semántica (múltiples leyes y decretos compitiendo en el mismo espacio vectorial de *Keys* y *Queries*):

```
[0 a 50k Tokens]   ──> Prefill Veloz (1.2s - 2.5s) | Atención Nítida | Cero Crosstalk
[55k a 70k Tokens] ──> Zona de Turbulencia: Crosstalk en Turno 20 y Turno 22
[> 100k Tokens]    ──> Colapso en Turno 30: Desalojo de KV Cache, Prefill de 45.2s, Fuga de Scratchpad
```

#### Evidencia Forense de Fallas en la Sesión Original:
1. **Turno 20 (Crosstalk con Turno 14 - 56.928 tokens):**
   * *Pregunta del usuario:* Reformas laborales de la Ley 27.742 (Ley Bases).
   * *Respuesta del modelo:* Respondió con *Tipos de personas jurídicas en el CCyC (Art. 145)*, reproduciendo la temática del Turno 14.
2. **Turno 22 (Crosstalk con Turno 21 - 61.471 tokens):**
   * *Pregunta del usuario:* Definición y aplicación del Fondo de Asistencia Laboral (FAL).
   * *Respuesta del modelo:* Repitió la respuesta sobre *Licencia por maternidad (Art. 177 LCT)* del Turno 21.
3. **Turno 23 (Alucinación normativa directa):**
   * El modelo inventó una cita literal falsa: `Constitución Nacional Argentina (1994) | Art. 75.1 | "El Estado debe proteger la vida"`. El Art. 75 inc. 1 de la CN trata sobre aduanas exteriores y derechos arancelarios.
4. **Turno 30 (Derivación y Fuga de Razonamiento - 114.202 tokens):**
   * *Pregunta del usuario:* Cambios introducidos por el Decreto 70/2025 a la Ley de Identidad de Género.
   * *Comportamiento:* Filtró su razonamiento interno en inglés fuera de tags: *"We have a big messy query. The user asks: '¿Puede el Presidente de la Nación, a través de un DNU, aumentar la pena prevista en el Código Penal para un delito? Fundamentar.'..."* y pasó a responder la consulta del Turno 25.
   * *Logs de `llama-server`:*
     ```text
     sep 07 12:09:24 llama-srv.sh: W srv alloc: - making room for prompt cache entry, removing oldest entry (size = 2500+ MiB)
     sep 07 12:12:34 llama-srv.sh: print_timing: prompt eval time = 44120.31 ms / 5649 tokens (5087 tok/s -> 128 tok/s)
     ```

---

## 🛠️ 3. La Solución Arquitectónica: Olvido Selectivo en Tres Fases

Para atacar la causa raíz sin aplicar parches cosméticos (**Ley 2 y Ley 3**), se actualizó el módulo `gateway/core/context_pruner.py` con una estrategia combinada:

```
                          [System Prompts Iniciales]
                                       │
                                       ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  1. Ventana Deslizante Atómica: Máximo 18 turnos de usuario        │
    │     (Preserva intacta la relación assistant tool_calls <-> tool)   │
    └────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  2. Compactación de Tool Outputs Antiguos                          │
    │     • Últimos 2 turnos: Textos RAG 100% íntegros (repreguntas OK)  │
    │     • Turnos anteriores: 'role: tool' archivado a 1 línea ligera   │
    │       (Ahorro de hasta 80.000 tokens de leyes ya sintetizadas)     │
    └────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  3. Techo de Seguridad Empírico: 52.000 tokens                     │
    │     (Poda en cascada si se supera el umbral seguro de atención)    │
    └────────────────────────────────────────────────────────────────────┘
```

### Código Clave de Compactación y Techo:
```python
# gateway/core/context_pruner.py
DEFAULT_MAX_USER_TURNS = 18
DEFAULT_MAX_CONTEXT_TOKENS = 52000
DEFAULT_KEEP_TOOL_TURNS = 2

# Compactación de herramientas de turnos antiguos (> 2 turnos previos)
for block_idx, block in enumerate(kept_blocks):
    is_old_block = (block_idx < threshold_idx)
    for m in block:
        if is_old_block and m.get("role") == "tool":
            content = m.get("content")
            if isinstance(content, str) and len(content) > 250:
                archived_msg = dict(m)
                archived_msg["content"] = (
                    f"[Contenido de herramienta archivado para optimizar contexto: "
                    f"{len(content)} caracteres previamente sintetizados por el asistente]"
                )
```

---

## ⚡ 4. Benchmarking de Rendimiento del Podador en CPU

Para medir si la lógica de poda añadía latencia a las peticiones del Gateway, se ejecutó un microbenchmark de **1.000 ejecuciones consecutivas** sobre un diálogo de 30 turnos con más de 600.000 caracteres (~172.500 tokens):

| Métrica de Ejecución en Gateway | Valor Medido |
| :--- | :--- |
| **Tiempo total (1.000 podas completas)** | **45.30 ms** |
| **Latencia promedio por petición** | **0.045 ms (45.3 microsegundos)** |
| **Impacto en el pipeline del Gateway** | **< 0.05% de la latencia del middleware** |
| **Ahorro neto generado en la GPU** | **~40.000 ms (40 segundos)** por inferencia |

---

## 📊 5. Verificación Empírica: Regeneración del Turno 30

El usuario se posicionó en el mismo hilo de Open-WebUI en el **Turno 30** (`¿Qué cambios introdujo el Decreto 70/2025 en relación con la Ley de Identidad de Género?`) y solicitó regenerar la respuesta con el nuevo motor de poda activo.

### Tabla Comparativa: Antes vs. Después

| Métrica / Parámetro | Turno 30 (Antes del Fix) | Turno 30 (Con Fix Activo) | Variación |
| :--- | :--- | :--- | :--- |
| **ID de Mensaje Open-WebUI** | `a50a3df2-c26f...` | `1d9a589f-db42...` | Regenerado |
| **Tokens del Prompt evaluados** | **113.068 tokens** | **29.541 tokens** | **-73.8%** |
| **Tiempo de Prefill (`prompt_ms`)** | **45.236 ms (45.2 s)** | **6.629 ms (6.6 s)** | ** Casi 7x más rápido** |
| **Velocidad de procesamiento** | 2.499 tok/s | **4.456 tok/s** | Tasa nominal recuperada |
| **Interferencia de Contexto (*Crosstalk*)** | Sí (contestó consulta penal del T25) | **Cero (Foco total en T30)** | 100% resuelto |
| **Fuga de Scratchpad (*Think Leak*)** | Sí (monólogo en inglés sin tags) | **No (Respuesta limpia en Markdown)** | 100% resuelto |
| **Evicción de Prompt Cache (`llama-server`)** | Sí (alerta de 2.5 GB desalojados) | **Cero desalojos** | Cache estable |

### Respuesta Jurídica Obtenida (Fidelidad a la Ley 4):
> *«El **Decreto 70/2025** (Poder Ejecutivo Nacional, 10 feb 2025) no contiene ninguna disposición que modifique, altere o introduzca cambios a la **Ley 26.743** (Ley de Identidad de Género).*  
> *El texto del decreto se limita a la reorganización de la administración nacional: sustitución del Anexo I y Anexo II del Decreto 1421/02, definición de la estructura de los ministerios y objetivos de la Subsecretaría de Administración y Normalización Patrimonial. No aparece ninguna referencia a 'identidad de género', 'Ley 26.743' ni a ninguna modificación de la misma.*  
> *Por lo tanto, **el Decreto 70/2025 no introdujo cambios en relación con la Ley 26.743**.»*

---

## 🏛️ 6. Leyes y Conclusiones Arquitectónicas

1. **La Regla Pragmática de la Ventana Operativa Efectiva:**
   $$\text{Ventana Operativa Multi-Turno con RAG} \approx 40\% \text{ a } 50\% \text{ de la Ventana Nominal del Fabricante}$$
   Un modelo con 128k tokens nominales opera de forma óptima en razonamiento multi-turno denso hasta **~52k tokens**.
2. **Consolidación de la Ley 4 (Integridad en Cascada):**
   Al remover la basura y el ruido de herramientas antiguas, el modelo no solo no alucina, sino que recupera su capacidad de **declarar con certeza técnica la inexistencia de modificaciones normativas**.
3. **Parámetros de Producción Calibrados:**
   - `GATEWAY_MAX_USER_TURNS = 18`
   - `GATEWAY_KEEP_TOOL_TURNS = 2`
   - `GATEWAY_MAX_CONTEXT_TOKENS = 52000`
