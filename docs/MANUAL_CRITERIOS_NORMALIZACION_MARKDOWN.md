# 🏛️ Manual Canónico de Criterios de Normalización de Markdown para RAG Jurídico

Este documento establece la **especificación técnica oficial y los criterios de normalización** para estructurar leyes, decretos, códigos, resoluciones y documentos jurídicos en **Markdown**. 

Su propósito es garantizar la **pureza en la ingesta y la fidelidad matemática del chunking jerárquico** en LanceDB (`app_rag_sync.py`), previniendo alucinaciones en cascada (**Ley 4 de Ingeniería**) y asegurando que el GPS semántico (`obtener_estructura_documento` y `leer_documento_completo`) funcione con máxima precisión.

---

## 📑 Tabla de Contenidos
1. [Principios Rectores e Invariantes](#1-principios-rectores-e-invariantes)
2. [Ficha de Metadatos y Frontmatter](#2-ficha-de-metadatos-y-frontmatter)
3. [Jerarquía Estructural de Encabezados (H1 a H5)](#3-jerarquía-estructural-de-encabezados-h1-a-h5)
4. [Formato Canónico del Articulado](#4-formato-canónico-del-articulado)
5. [Incisos, Apartados y Listas Normativas](#5-incisos-apartados-y-listas-normativas)
6. [Tablas Normativas (GFM)](#6-tablas-normativas-gfm)
7. [Notas Editoriales y Antecedentes (InfoLEG)](#7-notas-editoriales-y-antecedentes-infoleg)
8. [Higiene Tipográfica y Codificación de Caracteres](#8-higiene-tipográfica-y-codificación-de-caracteres)
9. [Catálogo de Antipatrones Prohibidos](#9-catálogo-de-antipatrones-prohibidos)
10. [Matriz de Auditoría y Reglas para Linter / IA](#10-matriz-de-auditoría-y-reglas-para-linter--ia)

---

## 1. Principios Rectores e Invariantes

Toda normalización de textos jurídicos —ya sea efectuada manualmente, mediante scripts deterministas (`fetch_infoleg.py`) o asistida por un auditor de IA— debe regirse por tres invariantes no negociables:

1. **Invariante de Fidelidad Textual Absoluta (Anti-Paráfrasis):**  
   * Jamás alterar la redacción, gramática, terminología ni puntuación original de la norma.
   * Prohibido modernizar o "corregir" giros legales arcaicos (*«fuese»*, *«concordatario»*, *«ut supra»*). Cada término tiene implicancias de hermenéutica jurídica.
2. **Invariante de No Omisión:**  
   * No omitir párrafos de promulgación (*«El Senado y Cámara de Diputados...»*), fórmulas de vigencia, artículos de forma (*«Comuníquese al Poder Ejecutivo...»*) ni cuadros anexos.
3. **Invariante de Compatibilidad RAG Jerárquica:**  
   * Toda sección, título o artículo debe formatearse de modo que el parser heurístico de LanceDB (`detect_heuristic_header`) pueda indexarlo sin amputar texto ni generar fragmentos descontextualizados.

---

## 2. Ficha de Metadatos y Frontmatter

Todo documento normativo debe comenzar con un encabezado `#` de Nivel 1 y un bloque de citas (`>`) que registre los metadatos institucionales oficiales:

```markdown
# LEY DE MODERNIZACION LABORAL Ley 27.802

> **Norma:** Ley 27802 PODER LEGISLATIVO NACIONAL (P.L.N.)
> **Rama / Categoría:** DERECHO LABORAL
> **Fecha:** 28-feb-2026
> **Publicación:** Publicada en el Boletín Oficial del 06-mar-2026 Número: 35860 Página: 1
> **Fuente Oficial:** [https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=409377](https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=409377)
>
> **Resumen Oficial:**
> REFORMA DEL RÉGIMEN DE CONTRATO DE TRABAJO. FONDO DE ASISTENCIA LABORAL. SISTEMA INTEGRADO DE PREVISIÓN.

---
```

### Reglas de los Metadatos:
* **Título H1:** Debe reflejar el nombre legal oficial (ej. `LEY 20.744 CONTRATO DE TRABAJO` o `DECRETO 70/2023 BASES...`).
* **Separador temático:** Inmediatamente después del bloque de metadatos, debe colocarse una línea divisoria `---`.
* **Texto preambular:** El texto introductorio de sanción se escribe como párrafo simple antes del primer encabezado `##`.

---

## 3. Jerarquía Estructural de Encabezados (H1 a H5)

El motor de chunking jerárquico de LanceDB mapea los niveles de encabezado para construir el «GPS Documental» (`Breadcrumb`). Por ende, los niveles de `#` deben ser estrictamente consistentes:

| Nivel Markdown | Rol en la Jerarquía Legal | Expresión Típica | Ejemplo Canónico |
| :---: | :--- | :--- | :--- |
| `#` (H1) | **Título de la Obra** | Nombre de la Ley / Código | `# CÓDIGO CIVIL Y COMERCIAL DE LA NACIÓN` |
| `##` (H2) | **Macro-Estructura / Bloque Mayor** | Libro, Parte o Sección Preliminar | `## LIBRO PRIMERO - Parte General`<br>`## CONSIDERANDO`<br>`## DECRETA:` |
| `###` (H3) | **Título de la Ley** | Título ordinal o romano | `### TÍTULO I - Disposiciones Generales`<br>`### TÍTULO II - Fondo de Asistencia Laboral (FAL)` |
| `####` (H4) | **Capítulo** | Capítulo ordinal o romano | `#### CAPÍTULO I - De los Sujetos`<br>`#### CAPÍTULO II - Competencia` |
| `#####` (H5) | **Sección Interna** | Sección ordinal o temática | `##### SECCIÓN 1ª - Notificaciones`<br>`##### SECCIÓN 2ª - Plazos Procesales` |

### Reglas de Encabezados:
1. **Obligatoriedad del Subtítulo Temático:**  
   Nunca dejar un encabezado truncado en el número (ej. `### TÍTULO II`). Si la ley contiene un subtítulo temático tras un salto de línea o nota editorial, debe unificarse en la misma línea con guion de separación:  
   * ❌ *Incorrecto:* `### TÍTULO II`  
   * 🟢 *Correcto:* `### TÍTULO II - Fondo de Asistencia Laboral (FAL)`
2. **Espaciado en Blanco:**  
   Todo encabezado `#` debe estar precedido y seguido por **exactamente una línea en blanco (`\n\n`)**.
3. **Prohibición de Negritas en Encabezados `#`:**  
   No combinar `#` con `**`. El símbolo `#` ya define el encabezado.  
   * ❌ *Incorrecto:* `### **TÍTULO I - De las Partes**`  
   * 🟢 *Correcto:* `### TÍTULO I - De las Partes`

---

## 4. Formato Canónico del Articulado

Los artículos constituyen la unidad fundamental de consulta jurídica. El parser de LanceDB está calibrado para extraer automáticamente el número de artículo y su epígrafe temático si se respeta el siguiente patrón exacto:

### Patrón Canónico con Epígrafe:
```markdown
**ARTÍCULO [N°]°.- [Epígrafe].** [Texto del primer párrafo...]
```

### Ejemplos Válidos:
* **Artículo estándar con epígrafe:**  
  `**ARTÍCULO 1°.- Objeto.** La presente ley rige en todo el territorio de la República...`
* **Artículo sin epígrafe formal:**  
  `**ARTÍCULO 14.-** Los plazos son perentorios e improrrogables...`
* **Artículo compuesto (bis, ter, quater):**  
  `**ARTÍCULO 245 bis.- Indemnización agravada.** Cuando el despido obedezca a...`
* **Artículo de forma final:**  
  `**ARTÍCULO 18°.-** Comuníquese, publíquese, dese a la Dirección Nacional del Registro Oficial y archívese.`

### Reglas Críticas del Articulado:
1. **Negrita Integral de la Cabecera:** Tanto la palabra `ARTÍCULO`, el número, el signo ordinal `°`, el punto y guion `.-` como el `Epígrafe` deben estar contenidos dentro del mismo bloque de negrita `**...**`.
2. **El Punto y Guion (`.-`):** El separador reglamentario entre el número/ordinal y el epígrafe debe ser `.-` o en su defecto `—` (guion largo tipográfico).
3. **Continuidad del Texto:** El texto del primer párrafo debe comenzar **en la misma línea** inmediatamente después del cierre de la negrita `**` con un espacio simple.
4. **Espaciado Inter-Artículo:** Entre el final del texto de un artículo y el inicio del siguiente debe existir **una línea en blanco (`\n\n`)**.

---

## 5. Incisos, Apartados y Listas Normativas

Las enumeraciones de causales, requisitos o facultades deben estructurarse como listas Markdown con sus identificadores resaltados en negrita para asegurar legibilidad y evitar que el chunker corte oraciones a mitad de concepto:

### Incisos Alfabéticos:
```markdown
**ARTÍCULO 6°.- Exclusiones.** Quedan excluidos del presente régimen:

* **a)** Los trabajadores contratados bajo el régimen de la Ley 22.250;
* **b)** El personal de casas particulares regido por la Ley 26.844;
* **c)** Los dependientes de la Administración Pública Nacional, provincial o municipal.
```

### Incisos Numéricos o Apartados:
```markdown
**ARTÍCULO 12°.- Requisitos.** Serán requisitos concurrentes:

* **1.** Contar con inscripción previa en el registro habilitado;
* **2.** Acreditar personería jurídica vigente;
* **3.** No registrar sanciones firmes en materia de seguridad social.
```

### Reglas de Listas:
* Usar siempre el asterisco (`*`) seguido de espacio y el identificador en negrita: `* **a)**` o `* **1.**`.
* Conservar el punto y coma (`;`) o punto (`.`) final que determine la norma.
* Si un inciso contiene sub-incisos (sub-puntos `i`, `ii`, `iii`), usar indentación de 2 o 4 espacios:
  ```markdown
  * **a)** Tratándose de personas jurídicas:
    * **i.** Copia certificada del estatuto social;
    * **ii.** Último balance aprobado.
  ```

---

## 6. Tablas Normativas (GFM)

Las alícuotas, escalas impositivas, indemnizaciones tarifadas u organigramas deben formatearse en **GitHub Flavored Markdown (GFM)**:

```markdown
| Tipo de Empresa | Alícuota General | Alícuota Reducida | Base Imponible |
| :--- | :---: | :---: | :--- |
| Grandes Empresas | 1,0 % | 0,8 % | SIPA (Art. 9° Ley 24.241) |
| MiPyMEs | 2,5 % | 1,5 % | SIPA (Art. 9° Ley 24.241) |
```

### Reglas de Tablas:
1. **Línea de Encabezado Obligatoria:** Toda tabla debe contar con una fila de títulos y una fila divisoria de guiones con indicación de alineación (`:---`, `:---:`, `---:`).
2. **Sin Saltos de Línea Internos:** Las celdas no deben contener saltos de línea físicos. Si se requiere separar conceptos dentro de una celda, usar `<br>`.
3. **Aislamiento:** La tabla debe estar separada del texto precedente y posterior por una línea en blanco.

---

## 7. Notas Editoriales y Antecedentes (InfoLEG)

InfoLEG inserta notas editoriales para advertir reformas, prórrogas o reglamentaciones (ej. `(Nota Infoleg: por art. 1° del Decreto N°... )`).

### Formato Canónico de Notas:
Deben mantenerse como párrafos en cursiva entre paréntesis o citas, **inmediatamente debajo del título o artículo que afectan**:

```markdown
### TÍTULO II - Fondo de Asistencia Laboral (FAL)

*(Nota Infoleg: por art. 27 del Decreto Nº 408/2026 B.O. 1/6/2026 se prorroga al 1° de noviembre de 2026 la entrada en vigencia del régimen establecido en el presente Título).*

**ARTÍCULO 58°.- Objeto.** Créanse los Fondos de Asistencia Laboral...
```

* **Prohibición:** Jamás colocar una nota editorial intercalada dentro de la línea de un encabezado (`### TÍTULO II (Nota Infoleg: ...)`). Esto rompe la detección del título en LanceDB.
* **Sección de Antecedentes:** Si al final de la norma se conserva la sección de antecedentes, rotularla con:
  ```markdown
  ---
  ## ANTECEDENTES NORMATIVOS
  ```

---

## 8. Higiene Tipográfica y Codificación de Caracteres

Los textos legales argentinos poseen convenciones tipográficas que deben preservarse estrictamente:

1. **Codificación Universal:** El archivo Markdown final debe guardarse estrictamente en **UTF-8 sin BOM**.
2. **Signo Ordinal Femenino y Masculino:**
   * Usar el carácter ordinal `°` (`U+00B0`) o `ª` (`U+00AA`) y no la letra 'o' volada o el cero:  
     🟢 `1°`, `2°`, `10°`, `1ª Sección`  
     ❌ `1o`, `10o`, `1ro`
3. **Guiones Tipográficos:**
   * Usar el guion largo (*em dash*) `—` (`U+2014`) o guion medio `–` (`U+2013`) para separar conceptos o epígrafes, preservando la tipografía formal del Boletín Oficial.
4. **Comillas Normativas:**
   * Preservar comillas tipográficas dobles (`“ ”`) o angulares latinas (`« »`). Evitar convertir comillas de cierre en caracteres de control invisibles.
5. **Espacios y Saltos de Línea:**
   * Normalizar retornos de carro estilo Windows (`\r\n`) a retornos UNIX simples (`\n`).
   * Eliminar espacios en blanco sobrantes al final de línea (*trailing whitespace*).
   * Colapsar secuencias de más de dos saltos de línea consecutivos (`\n\n\n+`) en exactamente dos saltos de línea (`\n\n`).

---

## 9. Catálogo de Antipatrones Prohibidos

Los siguientes 10 defectos estructurales rompen el RAG o inducen alucinaciones; deben ser corregidos sin excepción:

| # | Antipatrón Detectado | Impacto en el RAG / LanceDB | Forma Correcta |
| :-: | :--- | :--- | :--- |
| **1** | **Título huérfano sin subtítulo**<br>`### TÍTULO II` | El RAG no sabe de qué trata el título y no lo recupera por palabras clave temáticas. | `### TÍTULO II - Fondo de Asistencia Laboral (FAL)` |
| **2** | **Negrita incompleta en artículo**<br>`**ARTÍCULO 5°**.- Epígrafe.` | El epígrafe queda fuera del nombre de la sección en el GPS documental. | `**ARTÍCULO 5°.- Epígrafe.**` |
| **3** | **Artículo pegado a la palabra siguiente**<br>`ARTICULO 14Todos los plazos...` | El parser no detecta el número de artículo por colisión con el texto del cuerpo. | `**ARTÍCULO 14°.-** Todos los plazos...` |
| **4** | **Salto de línea interno en encabezado**<br>`### TÍTULO I`<br>`Disposiciones Generales` | El subtítulo queda registrado como un párrafo suelto huérfano. | `### TÍTULO I - Disposiciones Generales` |
| **5** | **Falso encabezado con asteriscos**<br>`**CAPÍTULO I - De las Obligaciones**` | LanceDB lo trata como Nivel 4 en vez de Nivel 3 o 2, rompiendo el árbol jerárquico. | `#### CAPÍTULO I - De las Obligaciones` |
| **6** | **Incisos sin lista Markdown**<br>`a) Requisito uno`<br>`b) Requisito dos` | Se compactan en una sola línea corrida al renderizar Markdown. | `* **a)** Requisito uno`<br>`* **b)** Requisito dos` |
| **7** | **Texto sin separación de párrafos** (bloque de 20.000 palabras) | El chunker corta oraciones a mitad de palabra o supera los límites de ventana. | Insertar `\n\n` entre cada párrafo o artículo. |
| **8** | **Etiquetas HTML residuales**<br>`<br>`, `<div>`, `<font size="2">` | Contaminan el contexto semántico de los embeddings y desperdician tokens. | Texto Markdown puro y limpio. |
| **9** | **Tabla rota o asimétrica**<br>Filas con distinto número de tuberías `\|` | Se rompe el renderizado en Open-WebUI y genera fragmentos corruptos. | Alinear columnas y asegurar igual número de celdas por fila. |
| **10** | **Omisión del Frontmatter / Metadatos** | El modelo desconoce si la norma está vigente, derogada o su fecha de publicación. | Incorporar siempre la ficha de metadatos oficial en bloque `>`. |

---

## 10. Matriz de Auditoría y Reglas para Linter / IA

Cuando se ejecute una auditoría asistida por IA o un script de verificación sobre un archivo `.md`, el validador debe escanear el texto línea por línea y emitir un reporte de diagnóstico conciso con las siguientes **coordenadas y códigos de falla**:

```markdown
### Reporte de Diagnóstico de Normalización

| Línea | Código | Gravedad | Fragmento Observado | Diagnóstico y Acción Sugerida |
| :---: | :---: | :---: | :--- | :--- |
| **142** | `ERR_TIT_TRUNC` | Alta | `### TÍTULO III` | Título sin subtítulo temático. Unificar con la descripción siguiente. |
| **289** | `ERR_ART_BOLD`  | Media | `**ARTÍCULO 12**.- Requisitos.` | Epígrafe fuera de la negrita. Corregir a: `**ARTÍCULO 12°.- Requisitos.**` |
| **405** | `ERR_HTML_TAG`  | Baja | `Texto con <font color="red">` | Etiqueta HTML residual. Reemplazar por formato Markdown o texto plano. |
| **512** | `ERR_INC_FMT`   | Media | `a) Presentar solicitud` | Inciso sin formato de lista. Corregir a: `* **a)** Presentar solicitud`. |
| **670** | `ERR_TAB_BROKEN`| Alta | `\| Col 1 \| Col 2` (falta barra) | Fila de tabla desalineada o sin cerrar. |
```

### Códigos Canónicos de Falla:
* `ERR_FRONTMATTER`: Falta el bloque de metadatos o la fuente oficial.
* `ERR_TIT_TRUNC`: Encabezado H2/H3/H4 amputado o sin subtítulo temático.
* `ERR_ART_SYNTAX`: Artículo sin palabra clave estándar, sin número o sin negrita `**...**`.
* `ERR_ART_BOLD`: Negrita cerrada antes del epígrafe o del punto y guion.
* `ERR_INC_FMT`: Incisos alfabéticos o numéricos no declarados como ítems de lista `* **x)**`.
* `ERR_HTML_TAG`: Presencia de tags HTML residuales (`<p>`, `<br>`, `<span>`, `<font>`).
* `ERR_TAB_BROKEN`: Tabla GFM con sintaxis rota o columnas desbalanceadas.
* `ERR_ENC_CORRUPT`: Caracteres de control invisibles o mojibake (`\x96`, ``).
