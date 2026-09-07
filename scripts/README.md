# 🛠️ Scripts y Herramientas del Repositorio

Esta carpeta contiene utilidades y scripts operacionales auxiliares para el mantenimiento, extracción de fuentes y sincronización del servidor vLLM Suite y la base de conocimiento RAG.

---

## 🏛️ Extractor de Normativas InfoLEG a Markdown (`fetch_infoleg.py`)

Script en Python diseñado para descargar leyes, decretos, reglamentaciones y códigos de **InfoLEG (Argentina)** y convertirlos automáticamente en **Markdown estructurado y jerarquizado**, listo para ser indexado por LanceDB (`app_rag_sync.py`) o procesado por `TECCAM_PDF`.

### 🚀 Uso Rápido:

#### Modo Interactivo (Pregunta por consola)
```bash
./scripts/fetch_infoleg.py
```

#### Modo Directo (Con argumentos)
```bash
./scripts/fetch_infoleg.py --url "https://servicios.infoleg.gob.ar/infolegInternet/verNorma.do?id=409377" --title "Decreto_70_2025"
```
O simplemente pasando el ID de la norma:
```bash
./scripts/fetch_infoleg.py --url "174117" --title "Ley_26639_Glaciares"
```

Los archivos resultantes se guardan en la subcarpeta [`scripts/output/`](output/).

> 📘 **Documentación completa y especificación técnica:**  
> Consulta el [**Manual de Extracción y Estructuración Normativa: InfoLEG a Markdown Jerárquico (`docs/MANUAL_EXTRACTOR_INFOLEG.md`)**](../docs/MANUAL_EXTRACTOR_INFOLEG.md).

---

## 🔍 Auditor y Linter Semántico de Markdown Legal (`audit_markdown.py`)

Script en Python diseñado para **auditar la calidad y estructura de los documentos Markdown** generados en `scripts/output/` contra las reglas oficiales de compatibilidad RAG en LanceDB.

En lugar de reescribir la ley (lo que arriesgaría alucinaciones o truncamientos), el script indexa cada renglón con coordenadas numéricas exactas (`linea: N`), inyecta el documento en un LLM de contexto extendido (DeepSeek o Gateway local) y emite un **reporte diagnóstico tabular de desvíos y anomalías**.

### 🚀 Uso Rápido:

#### Modo Interactivo (Menú con lista de documentos)
```bash
./scripts/audit_markdown.py
```

#### Modo Directo (Auditar un archivo específico)
```bash
./scripts/audit_markdown.py --file "LEY_DE_MODERNIZACION_LABORAL_Ley_27.802.md"
```

#### Opciones Avanzadas de Conexión:
```bash
# Apuntar directamente a la API de DeepSeek Cloud
./scripts/audit_markdown.py --file "Decreto_70_2025.md" --api-base "https://api.deepseek.com/v1" --api-key "$DEEPSEEK_API_KEY" --model "deepseek-chat"

# Usar el Gateway local especificando modelo
./scripts/audit_markdown.py --model "deepseek/deepseek-v4-flash"
```

Los reportes de auditoría se muestran en streaming en consola y se guardan automáticamente como `scripts/output/<norma>_auditoria.md`.

> 📘 **Manual Oficial de Criterios y Especificación Canónica:**  
> Consulta el [**Manual Canónico de Criterios de Normalización de Markdown para RAG Jurídico (`docs/MANUAL_CRITERIOS_NORMALIZACION_MARKDOWN.md`)**](../docs/MANUAL_CRITERIOS_NORMALIZACION_MARKDOWN.md).

