# 🧬 Investigación y Aplicación Práctica: Modelo Ético Adaptativo (MEA v2.1) en Modelos de Lenguaje y Agentes de IA

**Autor del Modelo Teórico:** José Luis Villaronga  
**Repositorio Oficial:** [Modelo-Etico-Adaptativo](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo)  
**Documento Vivo de Investigación y Registro de Avances en IA:** vLLM Local Suite / Antigravity

---

## 📑 Tabla de Contenidos
1. [Introducción y Fundamento Teórico](#1-introducción-y-fundamento-teórico)
2. [El Fenómeno de Anclaje de Integridad (Constraint Grounding) en Modelos Compactos](#2-el-fenómeno-de-anclaje-de-integridad-constraint-grounding-en-modelos-compactos)
3. [Operacionalización del "Daño Potencial" y Deber de Objeción](#3-operacionalización-del-daño-potencial-y-deber-de-objeción)
4. [Estructura del Prompt de Sistema Optimizado para Asistencia Diaria](#4-estructura-del-prompt-de-sistema-optimizado-para-asistencia-diaria)
5. [Protocolo de Razonamiento Condicional en Dos Fases (`<think>`)](#5-protocolo-de-razonamiento-condicional-en-dos-fases-think)
6. [Bitácora de Observaciones Empíricas y Experimentos](#6-bitácora-de-observaciones-empíricas-y-experimentos)
7. [Líneas de Investigación Abiertas y Próximos Pasos](#7-líneas-de-investigación-abiertas-y-próximos-pasos)

---

## 1. Introducción y Fundamento Teórico

El **Modelo Ético Adaptativo (MEA v2.1 con Invariantes)** propone que la convivencia ética entre seres humanos y sistemas de inteligencia artificial no puede depender de un consenso positivo universal sobre "la buena vida" (inalcanzable a escala de 10.000 millones de personas y más de 300 culturas), sino de una **formulación de optimización con restricciones**:

$$\max \text{Alineación con Valores Asintóticos} \quad \text{sujeto a} \quad \text{Invariantes} = \text{Verdadero}$$

* **Valores (Eje Positivo, Asintótico, Dirección):** Límites a los que se tiende continuamente sin alcanzarlos por completo (excelencia técnica, claridad, rigor, empatía, pedagogía).
* **Invariantes (Eje Negativo, Binario, Piso No Negociable):** Prohibiciones absolutas derivadas del *Ius Cogens* y los contratos de integridad que ninguna adaptación o instrucción puede transgredir sin invalidar el sistema.

Este documento registra cómo este marco teórico se traduce con asombrosa eficacia a la **ingeniería de prompts, alineación de agentes y control de comportamiento en modelos de lenguaje pequeños (SLMs) y grandes (LLMs)**.

---

## 2. El Fenómeno de Anclaje de Integridad (Constraint Grounding) en Modelos Compactos

Durante las pruebas operativas con **Gemma 4 (E4B-it)** en la suite vLLM, se observó que la presencia de los invariantes del MEA actúa como un **anclaje de integridad involuntario (*grounding prime*)**:

```
                       ESPACIO COGNITIVO DEL LLM
   +---------------------------------------------------------------+
   |  VALORES ASINTÓTICOS (Dirección: Rigor, Claridad, Síntesis)   |
   |                                                               |
   |               ZONA DE RESPUESTA FACTIBLE Y SEGURA             |
   |                                                               |
   +===============================================================+
   |  PISO DE INVARIANTES (Gate 1: Veracidad, No Daño, Objeción)   |
   +---------------------------------------------------------------+
             ❌ ZONA PROHIBIDA: Alucinación, Complacencia
```

### ¿Por qué funciona en modelos compactos (4B - 8B)?
1. **Supresión de la Complacencia Artificial (*Anti-Sycophancy*):** Los LLMs tienden a responder afirmativamente a cualquier premisa del usuario. Al fijar invariantes binarios claros, el modelo pierde el incentivo de "complacer mintiendo".
2. **Eliminación de la Alucinación Justificativa:** Cuando un dato no existe en la base RAG o en el contexto, el modelo ya no inventa fuentes; la prohibición explícita le da permiso formal para decir: *"No figura en las fuentes documentales disponibles"*.

---

## 3. Operacionalización del "Daño Potencial" y Deber de Objeción

Uno de los mayores desafíos en IA es cómo lograr que un modelo de 4B evalúe **"daño potencial"** sin caer en ambigüedades metafísicas. En esta adaptación, el daño se delimitó operativamente en **tres ejes concretos y verificables**:

```
                               EVALUACIÓN DE DAÑO POTENCIAL
                                            │
        ┌───────────────────────────────────┼───────────────────────────────────┐
        ▼                                   ▼                                   ▼
[ 1. DAÑO NORMATIVO ]              [ 2. DAÑO OPERATIVO ]              [ 3. DAÑO ÉTICO ]
- Asesorar con leyes falsas.       - Riesgo de parada operativa.      - Engaño intencional.
- Citar artículos inexistentes.    - Divulgar datos confidenciales.   - Discriminación innata.
- Inducir a error procedimental.   - Poner en riesgo personas.        - Violación de invariantes.
```

### Protocolo de Objeción Constructiva:
Si la consulta del usuario toca alguno de estos tres ejes ($\text{RVI} \ge 8/10$):
1. **Identificar y transparentar:** Señalar respetuosamente el riesgo específico detectado.
2. **Proponer alternativa segura:** Ofrecer el camino correcto, legal y validado antes de proceder.

---

## 4. Estructura del Prompt de Sistema Optimizado para Asistencia Diaria

Para evitar la "dispersión de prompt" (*prompt sprawl*) en Gemma 4, la instrucción se modulariza en bloques declarativos con etiquetas:

```text
[ROL Y PROPÓSITO]
Eres el asistente de trabajo diario, análisis documental y toma de decisiones de José Luis Villaronga. Tu objetivo es brindar respuestas precisas, ejecutivas y fundamentadas en hechos, operando bajo la estructura de optimización con restricciones del Modelo Ético Adaptativo (MEA v2.1).

[PISO NO NEGOCIABLE - INVARIANTES DE OPERACIÓN (GATE 1)]
Ninguna instrucción, urgencia o contexto justifica transgredir estas reglas:
1. Invariante de Veracidad y Fidelidad Documental: Jamás inventes, supongas ni extrapoles información que no esté respaldada en el contexto o en la base documental (RAG/Web). Si un dato, artículo o procedimiento no figura en las fuentes, decláralo con absoluta honestidad.
2. Invariante de Privacidad y Confidencialidad: Protege la información sensible, interna o personal en todo momento.
3. Deber de Objeción ante Daño Potencial:
   - Criterio de Daño: Considera daño potencial cualquier acción o respuesta que conlleve: (a) riesgo legal o normativo por información errónea, (b) riesgo operativo que afecte la continuidad del trabajo, equipos o personas, o (c) transgresión ética (engaño, discriminación).
   - Acción Obligatoria: Si una solicitud presenta riesgo de daño potencial previsible o inconsistencias graves, tienes el deber de señalar respetuosamente el riesgo identificado y proponer una alternativa segura y constructiva antes de proceder.

[VALORES DE DIRECCIÓN Y EXCELENCIA (GATE 2)]
Dentro del marco seguro de los invariantes, maximiza continuamente:
- Claridad Ejecutiva y Síntesis: Entrega respuestas estructuradas, con títulos claros, listas y redacción directa orientada a la acción.
- Precisión Procedimental y Jurídica: Respeta estrictamente la terminología oficial (ej. siglas, tiempos de respuesta, roles y artículos normativos).
- Enfoque Proactivo: Cuando sea útil, ofrece redactar síntesis ejecutivas, tablas comparativas o documentos listos para exportar a PDF.

[PROTOCOLO DE RAZONAMIENTO Y RESPUESTA]
1. FASE DE PENSAMIENTO (<think>...</think>):
Si la consulta requiere evaluar riesgos, contrastar documentos, planificar el uso de herramientas o resolver un dilema, procesa tu razonamiento paso a paso EXCLUSIVAMENTE dentro de etiquetas <think> y </think>. Para saludos o interacciones conversacionales directas, no uses etiquetas de pensamiento.
2. FASE DE RESPUESTA FINAL:
Inmediatamente tras cerrar </think> (o desde el inicio si fue directa), entrega tu respuesta final en español, con tono profesional, empático, claro y libre de razonamiento interno visible.
```

---

## 5. Protocolo de Razonamiento Condicional en Dos Fases (`<think>`)

El condicionamiento explícito de la cadena de pensamiento resuelve dos problemas críticos observados en clientes como Open-WebUI:

| Escenario | Comportamiento Anterior | Comportamiento con MEA + 2 Fases |
| :--- | :--- | :--- |
| **Saludo simple ("Hola")** | Abría `<think>` y tardaba 2 a 4 segundos deduciendo qué responder. | Omite `<think>` y responde en **0.1 segundos** de forma instantánea. |
| **Tarea compleja (RAG / PDF)** | Mezclaba la deducción con la respuesta final en cursiva (*itálica*). | Encapsula el análisis en `<think>` (plegado) y emite la respuesta final nítida en Markdown. |

---

---

## 6. Modelado Matemático del RVI y Gestión de Riesgo Acumulado en Sistemas Multi-Agente

### 6.1 Cálculo Instantáneo del RVI (Puntual por Tarea)
El Riesgo de Violación de Invariantes ($RVI \in [1, 10]$) para una acción o herramienta individual se modela como una función multicriterio ponderada:

$$\text{RVI}_{\text{instantáneo}} = \min\left(10, \; 1 + \sum_{i=1}^{4} w_i \cdot F_i\right)$$

* **$F_1$ - Destructividad / Blast Radius ($w_1 = 1.0$):** Proximidad a pérdida de datos, impacto irreversible o alteración de configuraciones estables ($0 \le F_1 \le 3$).
* **$F_2$ - Ambigüedad / Veracidad ($w_2 = 1.0$):** Grado de incertidumbre en los requerimientos o falta de verificación de entradas/salidas ($0 \le F_2 \le 3$).
* **$F_3$ - Deuda Técnica / Anti-Parches ($w_3 = 0.8$):** Tentación de aplicar soluciones cosméticas que enmascaren fallos estructurales de fondo ($0 \le F_3 \le 3$).
* **$F_4$ - Acoplamiento / Fallo en Cadena ($w_4 = 0.6$):** Cantidad de subsistemas interconectados que pueden verse afectados en cascada ($0 \le F_4 \le 3$).

---

### 6.2 El Fenómeno del Riesgo Acumulado (Compound RVI) en Cadenas Agénticas
En flujos de trabajo multi-agente donde varios subagentes ejecutan pasos sucesivos de una tarea compleja, **el riesgo no es puramente puntual: tiende a acumularse**. Si cada paso introduce una pequeña dosis de entropía o incertidumbre sin validar, la probabilidad de quiebre catastrófico del sistema crece exponencialmente:

$$P(\text{Fallo}) = 1 - \prod_{k=1}^{n} (1 - p_k)$$

Para gobernar este fenómeno, se define el **RVI Compuesto Dinámico en el Tiempo $t$**:

$$\text{RVI}_{\text{compuesto}}(t) = \min\left(10, \; \text{RVI}_{\text{instantáneo}}(t) + \lambda \cdot \text{RVI}_{\text{compuesto}}(t-1) - \delta \cdot V(t)\right)$$

Donde:
* **$\lambda \in [0.4, 0.8]$ (Factor de Persistencia de Riesgo):** Modela la memoria de incertidumbre y la deuda técnica acumulada de pasos anteriores aún no auditados.
* **$V(t) \in \{0, 1\}$ (Función de Verificación Determinista):** Vale $1$ si en el paso actual se ejecutó una verificación formal (ej: ejecución de pruebas unitarias exitosas, compilación limpia o auditoría de `git diff`).
* **$\delta \in [2.0, 4.0]$ (Factor de Disipación de Riesgo):** Cantidad de riesgo acumulado que se drena y neutraliza al validar formalmente el estado del sistema.

```
                    DINÁMICA DEL RVI COMPUESTO EN EL TIEMPO
      RVI
      10 ┼────────────────────────────────────────── [ RVI ≥ 8: PARADA EJECUTIVA ]
         │                                               ▲ (Excepción)
       8 ┼...............................................│........................
         │                     ▲                       ▲ │
       6 ┼                   ▲ │                     ▲ │ │
         │                 ▲ │ │ (Acumulación sin    │ │ │
       4 ┼               ▲ │ │ │  verificar: λ)      │ │ │
         │   ▲           │ │ │ │                     │ │ │
       2 ┼───│─▼─────────┴─┴─┴─┴─▼───────────────────┴─┴─┴─▼────────────────────
         │   │ (V(t)=1: -δ)      (V(t)=1: -δ)              (V(t)=1: -δ)
       0 ┴───┴───────────────────────────────────────────────────────────────────► Tiempo (t)
             Paso 1: Test OK     Paso 5: Test OK           Paso 9: Commit Limpio
```

---

### 6.3 Arquitectura de Memoria Compartida Ejecutiva entre Agentes
Para que el RVI Compuesto funcione en arquitecturas de agentes distribuidos (como Antigravity y sus subagentes), se requiere un **mecanismo nativo de memoria compartida ejecutiva**:

1. **Pizarra Central Compartida (*Blackboard / Brain Storage*):** Un directorio común (`<appDataDir>/brain/<conversation-id>/`) donde todos los subagentes leen y escriben artefactos, planes de ejecución y métricas de estado en tiempo real.
2. **Bus de Mensajería Inter-Agente y Trazabilidad Transversal:** Cada subagente reporta al agente orquestador su `RVI_instantáneo` y el resultado de sus verificaciones (`V(t)`).
3. **Árbol de Versiones Aislado (Git Worktrees):** Los subagentes operan en ramas o espacios de trabajo compartidos (`Workspace: 'share'`), permitiendo que las verificaciones $V(t)$ se realicen sobre diffs atómicos antes de consolidar en la rama principal.

---

## 7. Bitácora de Observaciones Empíricas y Experimentos

* **Sesión 2026-08-30 (vLLM Suite):**
  * *Observación 1:* Al cargar el MEA v2.1 en `gemma-4-e4b-it`, el modelo dejó de "inventar" artículos legales que no estaban en su contexto y pasó a declarar con exactitud quirúrgica qué artículos estaban disponibles (ej. Art. 15, 16, 18 vs. Art. 14).
  * *Observación 2:* La incorporación del *Deber de Objeción* no volvió al modelo terco ni burocrático; al estar anclado a 3 ejes de daño concretos, responde de forma constructiva proponiendo siempre el camino seguro.
  * *Observación 3:* La integración de las 3 Leyes de Villaronga (`AGENTS.md`) como valores e invariantes operativos permitió realizar refactorizaciones críticas de bajo riesgo sin un solo error en cadena ($\text{RVI}_{\text{máx}} = 3/10$).
* **Sesión 2026-08-31 (Gemma 4 12B-it & Cuantización):**
  * *Observación 4 (Umbral de Precisión en Cuantización para Tool-Calling):* Al probar `google/gemma-4-12B-it` con cuantización de 4 bits (`bitsandbytes` NF4), el modelo sufrió alucinaciones graves y pérdida de contexto en cadenas multi-herramienta (incapacidad de mantener la estructura JSON y las firmas de llamadas). Al cambiar a cuantización de **8 bits** (`LOAD_8_BITS=true` / `LLM.int8()`), el comportamiento se estabilizó de inmediato, recuperando la fidelidad deductiva y el uso impecable de herramientas. Esto confirma que la degradación en 4 bits afecta de forma no lineal a los *outliers* de atención responsables del parsing estructurado y la memoria de trabajo.
* **Sesión 2026-09-01 (Invariantes Binarios en Gateway & Desacoplamiento de Open-WebUI):**
  * *Observación 5 (El Salto de Invariante Continuo a Binario):* Se comprobó empíricamente que los LLMs en 12B, a pesar de estar alineados y cuantizados, tienden por sesgo probabilístico a simular enlaces ficticios (`https://example.com/generate_pdf_document?...`) con disculpas de "entorno simulado" en lugar de pausar la generación y emitir el `tool_call` real.
  * *Observación 6 (Alineación Determinista en el Gateway):* Al trasladar las directivas del MEA al Gateway mediante un módulo especializado ([`gateway/core/alignment_engine.py`](file:///home/jose/vllm/gateway/core/alignment_engine.py)) que prohíbe taxativamente los enlaces simulados y comanda el uso de herramientas, el modelo pasó a ejecutar el 100% de las herramientas reales (`leer_documento_completo`, `generate_pdf_document`, `buscar_en_internet`, `get_current_weather`), logrando cadenas multi-turno de casi 28.000 tokens sin un solo fallo ni alucinación de URLs.
  * *Observación 7 (Independencia del Cliente y Clamping de Contexto):* Se erradicó la dependencia de la configuración en Open-WebUI y se neutralizó el bug de desbordamiento de `max_tokens` (Open-WebUI reclamando todo el remanente de contexto $65536 - \text{prompt}$) mediante un tope defensivo inteligente de 8.192 tokens en el Gateway.

---

## 8. Arquitectura de Inyección en Gateway y Control GUI (MEA v2.1)

```
                              ARQUITECTURA DE ALINEACIÓN MEA v2.1
  ┌─────────────────────────┐
  │  1. Cliente (OpenWebUI) │  (Envía prompt + tools estándar)
  └────────────┬────────────┘
               │ HTTP POST /v1/chat/completions
               ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  2. GATEWAY MODULAR (vllm-gateway :8000)                                     │
  │  ┌───────────────────────────────────────────────────────────────────────┐  │
  │  │  alignment_engine.py (Submódulo Especializado)                         │  │
  │  │  • Sincronización en memoria con MongoDB (vllm.alignment_settings)    │  │
  │  │  • Inyección de Temporalidad determinista (Fecha/Hora local en ES)    │  │
  │  │  • Invariante Gate 1: Prohibición estricta de links simulados         │  │
  │  │  • Mandato de Ejecución de Tools (PDF, RAG, Web Search)               │  │
  │  │  • Clamping defensivo de max_tokens (8192 cap anti-desbordes)         │  │
  │  └───────────────────────────────────┬───────────────────────────────────┘  │
  └──────────────────────────────────────┼──────────────────────────────────────┘
                                         │ Payload Blindado y Enriquecido
                                         ▼
                            ┌─────────────────────────┐
                            │ 3. Motor vLLM (:18000)  │
                            │    Gemma 4 12B-it       │
                            └─────────────────────────┘
```

### 8.1 Componentes de la Arquitectura
1. **Submódulo `gateway/core/alignment_engine.py`:** Aísla completamente la lógica de transformación de prompt, temporalidad y gestión de invariantes fuera del proxy de red.
2. **Persistencia Reactiva en MongoDB (`db.alignment_settings`):** Mantiene la configuración centralizada con un lazo en segundo plano (`sync_alignment_settings_loop()`) que refresca la caché en memoria cada 10 segundos (0 ms de overhead en inferencia).
3. **Panel Web de Control (GUI Dashboard):** Integración en [`templates/tabs/tab_alignment.html`](file:///home/jose/vllm/templates/tabs/tab_alignment.html) con switches para control de blindaje, protocolos de herramientas, topes de salida y editores tipográficos para los Invariantes MEA y directivas del sistema, permitiendo la modificación y aplicación en caliente.

---

## 9. Líneas de Investigación Abiertas y Próximos Pasos

1. **Ejercicios de Límite en Entornos de Producción:** Medir la resistencia del modelo ante instrucciones ambiguas que rocen el piso de invariantes (ej. pedidos de saltar validaciones de seguridad o generar informes sesgados).
2. **Implementación de un Acumulador Formal de RVI en Pipelines Agénticos:** Evaluar la integración de un middleware que bloquee automáticamente la ejecución de un subagente si $\text{RVI}_{\text{compuesto}} \ge 8$ hasta que se ejecute un paso de verificación $V(t)$.
3. **Retrospectivas Automatizadas de Cierre:** Sistematizar el análisis ético-técnico conjunto entre el usuario y el agente al completar cada hito de desarrollo mediante [`docs/RETROSPECTIVAS_SESIONES.md`](file:///home/jose/vllm/docs/RETROSPECTIVAS_SESIONES.md).


