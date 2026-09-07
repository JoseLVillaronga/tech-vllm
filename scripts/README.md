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
