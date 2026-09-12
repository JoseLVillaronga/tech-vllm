# 📖 Doctrina de Investigación Exhaustiva y Marco Ontológico de Suficiencia RAG

**Ámbito:** Arquitectura RAG de vLLM Suite / CorpAI-Gen (Legal & Compliance)  
**Marco Teórico:** [Modelo Ético Adaptativo (MEA v2.1 con Invariantes)](https://github.com/JoseLVillaronga/Modelo-Etico-Adaptativo) y [Las Cuatro Leyes Universales](../../AGENTS.md)  
**Estado:** Canónico / Verificado en Producción (2026-09-12)

---

## 🏛️ 1. Fundamento Filosófico: Guía Positiva Ontológica vs. Micromanager Imperativo

Los modelos de lenguaje avanzados con altas capacidades de razonamiento (como la familia Gemma 4 y arquitecturas afines) no requieren microgestión imperativa (*"Paso 1: debes hacer X obligatoriamente, Paso 2: tienes prohibido hacer Y"*). El exceso de mandatos procedimentales rígidos genera dos efectos adversos:
1. **Rigidización Burocrática:** El modelo trata las directivas como un checklist formal, respondiendo de manera acartonada o narrando en voz alta lo que va a hacer en lugar de actuar.
2. **Fragilidad ante Situaciones Complejas:** Ante consultas que escapan al flujo rígido previsto, el modelo se desorienta y no sabe cómo adaptar su estrategia.

En su lugar, la **Doctrina de Investigación Exhaustiva** se fundamenta en la **Guía Positiva Ontológica**:
> *En lugar de dictarle al modelo cómo debe moverse paso a paso, se le dota de la definición de qué constituye un estado de verdad, rigor y suficiencia probatoria para cada tipo de problema.*

Al comprender **qué ES** una investigación exhaustiva en sus diferentes dimensiones, el modelo selecciona y orquesta autónomamente las herramientas adecuadas según la naturaleza intrínseca de la consulta.

---

## 🗺️ 2. Las Tres Modalidades Canónicas de Investigación RAG

Toda investigación documental o jurídica rigurosa en el sistema se articula a través de tres modalidades complementarias de suficiencia probatoria:

```
                              ┌────────────────────────────────────────┐
                              │     TIPOS DE INVESTIGACIÓN RAG         │
                              └──────────────────┬─────────────────────┘
                                                 │
         ┌───────────────────────────────────────┼──────────────────────────────────────┐
         ▼                                       ▼                                      ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐   ┌─────────────────────────────┐
│  1. SEMÁNTICA ORTOGONAL     │   │  2. JERÁRQUICA DETERMINISTA │   │  3. COMBINADA (PINPOINT)    │
│  • Multi-query en paralelo  │   │  • Top-Down (Macro a Micro) │   │  • Detección semántica      │
│  • Descomposición en ejes   │   │  • Catálogo ➔ GPS ➔ Lectura │   │  • Lectura de articulado    │
│    independientes           │   │  • Cero lagunas en códigos  │   │    íntegro sin recortes     │
└─────────────────────────────┘   └─────────────────────────────┘   └─────────────────────────────┘
```

---

### 🔹 Modalidad 1: Búsqueda Semántica Ortogonal (Descomposición Multifacética)

* **Definición Ontológica:**  
  Una investigación es *semánticamente exhaustiva* cuando una problemática compleja, transversal o de conflicto normativo es descompuesta en sus **dimensiones conceptuales independientes (ortogonales)**, explorando cada una en paralelo mediante `buscar_en_base_de_conocimiento` sin incurrir en redundancias textuales.
* **Criterio de Aplicación:**
  - Consultas que cruzan dos o más ordenamientos o figuras jurídicas (ej.: *relación entre un tratado internacional y una ley de presupuestos mínimos*).
  - Problemas con múltiples pretensiones analíticas (marco general, régimen especial, nexo relacional y objeto de tutela).
* **Mecánica Operativa:**
  - El modelo formula consultas simultáneas no redundantes (ej.: Consulta A: marco internacional; Consulta B: ley local; Consulta C: articulado de articulación; Consulta D: definiciones dogmáticas).
  - El Gateway intercepta y valida las llamadas: deduplica en caso de repeticiones accidentales y permite la ejecución concurrente en LanceDB (~150 ms por llamada).
* **Caso Testigo Verificado:**
  - Consulta: *"Analiza la relación entre el Tratado Antártico y la Ley de Protección de Glaciares, fundamenta"*.
  - Descomposición: 4 llamadas independientes cubriendo relación, Ley 26.639, Ley 15.802 y definición de glaciar.
  - Resultado: Recuperación instantánea del **Artículo 16° de la Ley 26.639** (cláusula de sujeción al Tratado Antártico y Protocolo de Madrid) y fundamentación perfecta en 644 tokens.

---

### 🔹 Modalidad 2: Búsqueda Jerárquica Determinista (Navegación Top-Down)

* **Definición Ontológica:**  
  Una investigación es *jerárquicamente exhaustiva* cuando el valor de la prueba y la interpretación dependen estrictamente de la **topología sistemática del cuerpo normativo**, avanzando de manera determinista desde el macro-catálogo hasta el texto dispositivo literal, sin atajos probabilísticos.
* **Criterio de Aplicación:**
  - Códigos extensos, leyes orgánicas, estatutos o reglamentos densos (Código Penal, Código Civil y Comercial, Ley de Bases, LCT).
  - Consultas donde un artículo aislado puede inducir a error si se descontextualiza de su Título, Capítulo o Libro (ej.: distinguir causales de nulidad relativa de absoluta, o tipos de homicidio).
* **Secuencia Canónica de 3 Pasos:**
  1. **Macro / Catálogo General (`obtener_indice_biblioteca`):**  
     Verificación de la existencia de la obra en la biblioteca, su estado de vigencia (`[VIGENTE]` vs `[DEROGADO]`) y su `doc_id` oficial.  
     *Axioma:* El índice contiene únicamente metadatos orientativos; está estrictamente prohibido fundamentar o inferir el contenido dispositivo de una norma basándose solo en su título en el índice.
  2. **Medio / GPS Estructural (`obtener_estructura_documento`):**  
     Mapeo del árbol de secciones, libros y capítulos (utilizando el parámetro `filtro` si corresponde). Permite situar el capítulo rector exacto y no saltar a áreas inconexas.
  3. **Micro / Lectura Dispositiva Oficial (`leer_documento_completo`):**  
     Invocación focalizada de la sección o capítulo puntual identificado en el paso previo para extraer el texto dispositivo literal con sus incisos completos y sin truncamientos.
* **Caso Testigo Verificado:**
  - Consulta: *"¿Qué delitos se regulan en el Título I del Libro II del Código Penal argentino?"*.
  - Navegación: `obtener_estructura_documento(doc_id="...", filtro="Libro II")` $\rightarrow$ `leer_documento_completo(seccion="TITULO I - DELITOS CONTRA LAS PERSONAS")` (~5.466 tokens).
  - Resultado: Desglose canónico exhaustivo de Arts. 79 al 108 (homicidios, aborto, lesiones, duelo, abandono) sin lagunas ni omisiones.

---

### 🔹 Modalidad 3: Estrategia Combinada (Aterrizaje Semántico + Cirugía Estructural)

* **Definición Ontológica:**  
  Una investigación es *combinada (híbrida)* cuando utiliza la búsqueda semántica como **sensor de aproximación rápida** para identificar la norma y el artículo clave, y de inmediato activa la **lectura estructural sistemática** para extraer el articulado íntegro, sus incisos, excepciones y régimen sancionatorio sin depender de los límites de fragmentación (*chunk size*) de los embeddings.
* **Criterio de Aplicación:**
  - Peticiones que exigen *"fundamentar en profundidad"*.
  - Determinación de listas taxativas de causales, requisitos formales, escalas penales o condiciones de validez/eficacia.
* **Mecánica Operativa:**
  - Paso 1: `buscar_en_base_de_conocimiento` localiza fragmentos preliminares y el `doc_id` relevante.
  - Paso 2: Si el fragmento recuperado está cortado, contiene referencias a incisos no desglosados o requiere el contexto del capítulo, el modelo ejecuta `obtener_estructura_documento` o `leer_documento_completo(seccion="...")`.
  - Paso 3: Síntesis integral con citas cruzadas entre el texto literal y los principios rectores.
* **Caso Testigo Verificado:**
  - Consulta: *"¿Cuáles son las notas tipificantes de la relación de dependencia según la LCT?"*.
  - Procedimiento: `buscar_en_base_de_conocimiento` $\rightarrow$ `obtener_indice_biblioteca` $\rightarrow$ `obtener_estructura_documento` (Arts. 21 a 23) $\rightarrow$ Lectura de artículos clave.
  - Resultado: Distinción dogmática perfecta entre subordinación técnica, económica y jurídica (Art. 21) y presunción legal de laboralidad (Art. 23).

---

## 🚫 3. Los Cuatro Antipatrones de Falsa Exhaustividad (Invariantes MEA)

Para garantizar la pureza de la síntesis según la **Ley 4 (Integridad en Cascada)**, el sistema define cuatro estados de corrupción que anulan la validez de una investigación:

| Antipatrón | Manifestación Patológica | Principio MEA Transgredido |
| :--- | :--- | :--- |
| **Literalismo Ciego de Docstring** | Copiar IDs de ejemplo de las descripciones de herramientas en lugar de consultar la base de datos real. | Invariante de Veracidad y Grounding. |
| **Alucinación Sustitutiva por Vacío** | Inventar números de artículos o contenidos apócrifos cuando la búsqueda semántica no devuelve el texto exacto. | Ley 4: Alucinación inducida por contexto viciado. |
| **Degeneración Metadiscursiva (*Narrative Loop*)** | Escribir en texto visible promesas en futuro (*"procederé a buscar...", "se ejecutará una consulta..."*) sin emitir la llamada formal a la herramienta. | Invariante de Integridad de Ejecución. |
| **Anclaje Forzado (*Crosstalk*)** | Forzar la inclusión de figuras incidentales mencionadas en fragmentos secundarios desviando la respuesta de la consulta original. | Foco Perentorio en Consulta Actual. |

---

## ⚖️ 4. La Regla de Oro de la Transparencia Radical

> *Ante la ausencia de evidencia documental en la base de conocimiento local (ej.: jurisprudencia no indexada, leyes específicas ausentes o normas derogadas), la respuesta de mayor rigor técnico no es la síntesis forzada, sino la **declaración explícita, honesta y transparente de la inexistencia de fuentes** en la sesión actual.*

Un modelo que declara ignorancia fundamentada preserva la confianza del usuario y la integridad del sistema; un modelo que inventa o aproxima normas para complacer al usuario destruye la seguridad jurídica del entorno corporativo.
