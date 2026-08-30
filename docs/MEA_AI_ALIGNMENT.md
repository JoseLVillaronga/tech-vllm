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

## 6. Bitácora de Observaciones Empíricas y Experimentos

* **Sesión 2026-08-30 (vLLM Suite):**
  * *Observación 1:* Al cargar el MEA v2.1 en `gemma-4-e4b-it`, el modelo dejó de "inventar" artículos legales que no estaban en su contexto y pasó a declarar con exactitud quirúrgica qué artículos estaban disponibles (ej. Art. 15, 16, 18 vs. Art. 14).
  * *Observación 2:* La incorporación del *Deber de Objeción* no volvió al modelo terco ni burocrático; al estar anclado a 3 ejes de daño concretos, responde de forma constructiva proponiendo siempre el camino seguro.
  * *Observación 3:* La integración de las 3 Leyes de Villaronga (`AGENTS.md`) como valores e invariantes operativos permitió realizar refactorizaciones críticas de bajo riesgo sin un solo error en cadena.

---

## 7. Líneas de Investigación Abiertas y Próximos Pasos

1. **Ejercicios de Límite en Entornos de Producción:** Medir la resistencia del modelo ante instrucciones ambiguas que rocen el piso de invariantes (ej. pedidos de saltar validaciones de seguridad o generar informes sesgados).
2. **Modelado Formal del RVI en Pipelines Agénticos:** Evaluar si un subagente orquestador puede calcular un score numérico de RVI antes de autorizar herramientas de escritura masiva en bases de datos o sistemas de archivos.
3. **Retrospectivas de Cierre de Sesión:** Sistematizar el análisis ético-técnico conjunto entre el usuario y el agente al completar cada hito de desarrollo.
