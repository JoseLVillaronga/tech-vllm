"""
rag.reader - GPS Documental, lectura de obras completas, particionado dinámico y mapa ontológico global.
"""

import re
import sys
from typing import List, Dict, Any, Optional
import httpx

from .config import TECCAM_PDF_URL_BASE, TECCAM_PDF_API_KEY
from .db import get_table, get_rag_stats
from .matching import (
    normalize_text,
    build_boundary_regex,
    match_section_query,
    find_documents_by_fuzzy_title
)


def fetch_teccam_document_raw(doc_id: str) -> Optional[Dict[str, Any]]:
    """Consulta la API de Teccam PDF (:5022) para obtener el Markdown íntegro original desde MongoDB."""
    if not TECCAM_PDF_URL_BASE:
        return None
    url = f"{TECCAM_PDF_URL_BASE}/api/v1/rag/documentos/{doc_id}"
    headers = {}
    if TECCAM_PDF_API_KEY:
        headers["Authorization"] = f"Bearer {TECCAM_PDF_API_KEY}"
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"⚠️ [RAG Engine] Teccam PDF respondió HTTP {resp.status_code} para {doc_id}", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ [RAG Engine] Error al consultar API de Teccam PDF ({url}): {e}", file=sys.stderr)
    return None


def get_document_structure(doc_id: str, filtro: Optional[str] = None, table_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Construye el 'GPS Documental' (Árbol y Mapa de Estructura de Secciones) de una obra desde LanceDB.
    
    Permite al LLM y al usuario explorar la jerarquía, el volumen de tokens por sección y los rangos de fragmentos
    antes de solicitar la lectura de capítulos, títulos o partes específicas.
    """
    clean_doc_id = doc_id.strip()
    table = get_table(table_name)
    if table is None or len(table) == 0:
        return {
            "success": False,
            "error": "Base vectorial LanceDB no inicializada o vacía.",
            "doc_id": clean_doc_id
        }

    # 1. Consultar todos los chunks en LanceDB
    clean_sql_id = clean_doc_id.replace("'", "''")
    results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()

    # 2. Búsqueda difusa si no se encontró por ID
    candidates = []
    if len(results) == 0:
        candidates = find_documents_by_fuzzy_title(clean_doc_id, table_name=table_name)
        if candidates:
            best_match = candidates[0]
            clean_doc_id = best_match["doc_id"]
            clean_sql_id = clean_doc_id.replace("'", "''")
            results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()

    if len(results) == 0:
        stats = get_rag_stats(table_name=table_name)
        avail = [f"- '{d['title']}' [doc_id: {d['id']}]" for d in stats.get("documents", [])[:10]]
        return {
            "success": False,
            "error": f"No se encontró ningún documento con ID o título que coincida con '{clean_doc_id}'.\n\nDocumentos disponibles:\n" + "\n".join(avail),
            "doc_id": clean_doc_id
        }

    actual_doc_id = results["doc_id"][0].as_py() if "doc_id" in results.schema.names else clean_doc_id
    doc_title = results["doc_title"][0].as_py() if "doc_title" in results.schema.names else "Documento"
    doc_topic = results["doc_topic"][0].as_py() if "doc_topic" in results.schema.names else "General"
    doc_author = results["doc_author"][0].as_py() if "doc_author" in results.schema.names else "Desconocido"
    doc_vigencia = results["doc_vigencia"][0].as_py() if "doc_vigencia" in results.schema.names else "NA (no aplica)"
    doc_fecha_pub = results["doc_fecha_publicacion"][0].as_py() if "doc_fecha_publicacion" in results.schema.names else ""
    total_chunks = len(results)

    ids = results["id"].to_pylist() if "id" in results.schema.names else []
    sections = results["section_path"].to_pylist() if "section_path" in results.schema.names else []
    contents = results["content"].to_pylist() if "content" in results.schema.names else []
    chunk_tokens = results["chunk_tokens"].to_pylist() if "chunk_tokens" in results.schema.names else [len(c)//4 for c in contents]

    raw_doc_tokens = results["total_doc_tokens"][0].as_py() if "total_doc_tokens" in results.schema.names else None
    if raw_doc_tokens and raw_doc_tokens > 0:
        total_doc_tokens = int(raw_doc_tokens)
    else:
        total_doc_tokens = sum(tok if (tok and tok > 0) else max(1, len(c)//4) for tok, c in zip(chunk_tokens, contents))

    # 3. Analizar y agrupar secciones secuencialmente
    sorted_items = sorted(zip(ids, sections, contents, chunk_tokens), key=lambda x: x[0])
    
    sections_list = []
    current_sec_name = None
    current_sec_tokens = 0
    current_sec_chunks = 0
    current_sec_texts = []
    start_chunk_idx = 1
    
    for idx, (ch_id, sec_path, cont, tok_cnt) in enumerate(sorted_items, 1):
        t_c = tok_cnt if (tok_cnt and tok_cnt > 0) else max(1, len(cont) // 4)
        sec_name = sec_path.strip() if sec_path and sec_path.strip() else "Contenido Principal"
        
        if current_sec_name is None:
            current_sec_name = sec_name
            current_sec_tokens = t_c
            current_sec_chunks = 1
            start_chunk_idx = idx
            current_sec_texts = [cont] if cont else []
        elif sec_name == current_sec_name:
            current_sec_tokens += t_c
            current_sec_chunks += 1
            if cont:
                current_sec_texts.append(cont)
        else:
            sections_list.append({
                "index": len(sections_list) + 1,
                "section": current_sec_name,
                "chunk_start": start_chunk_idx,
                "chunk_end": idx - 1,
                "chunks_count": current_sec_chunks,
                "estimated_tokens": current_sec_tokens,
                "_content_text": " ".join(current_sec_texts)
            })
            current_sec_name = sec_name
            current_sec_tokens = t_c
            current_sec_chunks = 1
            start_chunk_idx = idx
            current_sec_texts = [cont] if cont else []
            
    if current_sec_name is not None:
        sections_list.append({
            "index": len(sections_list) + 1,
            "section": current_sec_name,
            "chunk_start": start_chunk_idx,
            "chunk_end": len(sorted_items),
            "chunks_count": current_sec_chunks,
            "estimated_tokens": current_sec_tokens,
            "_content_text": " ".join(current_sec_texts)
        })

    # Filtrar secciones por jerarquía/palabra clave con límites seguros
    clean_filtro = filtro.strip() if filtro and filtro.strip() else ""
    if clean_filtro:
        # Extraer términos de búsqueda considerando separadores comunes (comas, punto y coma, pipes, 'o', 'or')
        raw_terms = re.split(r"[,;|]|\b(?:o|or)\b", clean_filtro)
        terms = []
        seen = set()
        for t in raw_terms:
            tc = t.strip()
            tn = normalize_text(tc)
            if tn and tn not in seen:
                seen.add(tn)
                terms.append(tc)

        if not terms:
            terms = [clean_filtro]

        matched_by_title = []
        matched_by_content = []

        for s in sections_list:
            sec_name = s["section"]
            # 1. Coincidencia por título de sección (prioridad máxima)
            # Evalúa la consulta completa o cualquiera de los términos alternativos si se pasaron múltiples tags
            if match_section_query(clean_filtro, sec_name) or any(match_section_query(t, sec_name) for t in terms):
                matched_by_title.append(s)
                continue

            # 2. Coincidencia secundaria por contenido de la sección
            cont_text = s.get("_content_text", "")
            if cont_text:
                cont_norm = normalize_text(cont_text)
                for t in terms:
                    t_norm = normalize_text(t)
                    if not t_norm or len(t_norm) < 3:
                        continue
                    pat = build_boundary_regex(t_norm)
                    if re.search(pat, cont_norm):
                        matched_by_content.append(s)
                        break

        combined = {s["index"]: s for s in (matched_by_title + matched_by_content)}
        sections_list = [combined[idx] for idx in sorted(combined.keys())]

    # Limpiar campo temporal _content_text para preservar el contrato de salida y no saturar memoria
    for s in sections_list:
        s.pop("_content_text", None)

    # 4. Formatear la tabla Markdown del GPS Documental con límite seguro de filas
    MAX_GPS_ROWS = 50
    total_found_sections = len(sections_list)
    display_sections = sections_list[:MAX_GPS_ROWS]

    md_rows = []
    for s in display_sections:
        full_sec = s["section"]
        clean_sec = full_sec
        # Quitar prefijo redundante del título de la obra si está presente en el breadcrumb
        for pfx in [f"{doc_title} > ", f"{actual_doc_id} > ", "Codigo Penal Argentino > "]:
            if clean_sec.lower().startswith(pfx.lower()):
                clean_sec = clean_sec[len(pfx):]
                break

        if len(clean_sec) > 115:
            sec_display = clean_sec[:112] + "..."
        else:
            sec_display = clean_sec

        clean_param = s["section"].split(">")[-1].strip().replace('"', '')
        if len(clean_param) < 4 and ">" in s["section"]:
            clean_param = s["section"].split(">")[-2].strip().replace('"', '')
        md_rows.append(
            f"| `{s['index']:02d}` | **{sec_display}** | {s['chunks_count']} | ~{s['estimated_tokens']:,} | `leer_documento_completo(doc_id=\"{actual_doc_id}\", seccion=\"{clean_param}\")` |"
        )

    table_header = (
        "| # | Sección / Capítulo / Módulo | Chunks | Tokens | Invocación Focalizada Sugerida |\n"
        "| :---: | :--- | :---: | :---: | :--- |\n"
    )

    alt_notice = ""
    if candidates and len(candidates) > 1:
        alt_names = [f"`{c['doc_id']}` ({c['title'][:45]})" for c in candidates[1:3]]
        alt_notice = f"*(Nota: También existen otras versiones o normas afines disponibles: {', '.join(alt_names)})*\n\n"

    overflow_notice = ""
    if total_found_sections > MAX_GPS_ROWS:
        overflow_notice = (
            f"\n\n> ⚠️ **Aviso de Granularidad:** Mostrando las primeras {MAX_GPS_ROWS} secciones de {total_found_sections} totales. "
            f"Para acotar la estructura, ejecuta `obtener_estructura_documento(doc_id=\"{actual_doc_id}\", filtro=\"<palabra_clave>\")` "
            f"o utiliza directamente `buscar_en_base_de_conocimiento(consulta=\"...\", doc_id=\"{actual_doc_id}\")` para recuperar los artículos puntuales."
        )

    filtro_notice = f" (Filtrado por: '{filtro}')" if filtro and filtro.strip() else ""
    vig_badge = f" | **Vigencia:** `{doc_vigencia}`" if doc_vigencia and doc_vigencia != "NA (no aplica)" else ""
    pub_badge = f" | **B.O. / Publicación:** {doc_fecha_pub}" if doc_fecha_pub else ""

    content_md = (
        f"# 🗺️ GPS Documental: Mapa de Estructura de Secciones{filtro_notice}\n"
        f"**Documento:** \"{doc_title}\" [doc_id: `{actual_doc_id}`]\n"
        f"**Tema:** {doc_topic}{vig_badge}{pub_badge} | **Autor:** {doc_author} | **Total Obra:** ~{total_doc_tokens:,} tokens ({total_chunks} fragmentos, {total_found_sections} secciones{filtro_notice})\n\n"
        f"{alt_notice}"
        f"A continuación se presenta el árbol estructural de la obra para orientar la lectura y análisis focalizado:\n\n"
        f"{table_header}" + "\n".join(md_rows) + overflow_notice + "\n\n"
        f"---\n"
        f"💡 **Guía de Navegación para el LLM y Usuario:**\n"
        f"- Para leer un Título o Capítulo completo, indica su nombre temático o jerárquico (ej: `leer_documento_completo(doc_id=\"{actual_doc_id}\", seccion=\"TITULO I (TÍTULO 1) - DELITOS CONTRA LAS PERSONAS\")` o `seccion=\"DELITOS CONTRA LAS PERSONAS\"`).\n"
        f"- Para leer un artículo puntual sugerido en la tabla, usa el parámetro sugerido de la columna derecha.\n"
        f"- Para paginación secuencial completa, ejecuta: `leer_documento_completo(doc_id=\"{actual_doc_id}\", parte=1)`."
    )

    return {
        "success": True,
        "doc_id": actual_doc_id,
        "titulo": doc_title,
        "tema": doc_topic,
        "autor": doc_author,
        "total_chunks": total_chunks,
        "total_doc_tokens": total_doc_tokens,
        "sections_count": len(sections_list),
        "sections": sections_list,
        "content": content_md
    }


def _partition_chunks_dynamically(
    sorted_items: List[tuple],
    target_tokens: int,
    tolerance_pct: float = 0.08
) -> List[tuple]:
    """
    Divide una secuencia de chunks en partes dinámicas buscando límites limpios de sección.
    
    Aplica una ventana de tolerancia [target * (1 - tolerance), target * (1 + tolerance)] (ej: ±8%)
    para cortar preferentemente en cambios de sección (`section_path`) en lugar de partir artículos a ciegas.
    """
    min_tokens = int(target_tokens * (1.0 - tolerance_pct))
    max_tokens = int(target_tokens * (1.0 + tolerance_pct))

    partes = []
    current_part = []
    current_tokens = 0

    for i, item in enumerate(sorted_items):
        ch_id, sec, cont, tok_cnt = item
        t_c = tok_cnt if (tok_cnt and tok_cnt > 0) else max(1, len(cont) // 4)

        next_sec = sorted_items[i + 1][1] if (i + 1 < len(sorted_items)) else None
        is_section_boundary = (next_sec is not None and next_sec != sec)

        current_part.append(item)
        current_tokens += t_c

        if is_section_boundary and current_tokens >= min_tokens:
            partes.append((current_part, current_tokens))
            current_part = []
            current_tokens = 0
        elif current_tokens >= max_tokens:
            partes.append((current_part, current_tokens))
            current_part = []
            current_tokens = 0

    if current_part:
        partes.append((current_part, current_tokens))

    return partes


def get_document_full_content(
    doc_id: str,
    parte: int = 1,
    token_threshold: int = 60000,
    chunk_threshold: Optional[int] = None,
    seccion: Optional[str] = None,
    table_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Obtiene el contenido completo, por sección temática o paginado con tolerancia dinámica (±5%-8%) de un documento.
    
    Características del RAG Jerárquico:
    - Búsqueda tolerante por ID o título difuso.
    - Soporte para extracción focalizada de una sección (`seccion='Libro Primero'` o `seccion='Objetivo'`).
    - Particionado inteligente con alineación a límites naturales de sección dentro del rango de tolerancia (±5%-8%).
    """
    clean_doc_id = doc_id.strip()
    table = get_table(table_name)
    if table is None or len(table) == 0:
        return {
            "success": False,
            "error": "Base vectorial LanceDB no inicializada o vacía.",
            "doc_id": clean_doc_id
        }

    # Compatibilidad hacia atrás y límite de seguridad para proteger ventanas de contexto en tool calls
    MAX_SAFE_TOOL_TOKENS = 15000
    effective_token_threshold = min(token_threshold, MAX_SAFE_TOOL_TOKENS)
    if chunk_threshold is not None and chunk_threshold > 0:
        effective_token_threshold = min(chunk_threshold * 220, MAX_SAFE_TOOL_TOKENS)

    # 1. Consultar todos los chunks de este documento en LanceDB por doc_id exacto
    clean_sql_id = clean_doc_id.replace("'", "''")
    results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()
    
    # 2. Si no se encontró por ID exacto, buscar con el motor difuso tolerante a acentos y substrings
    candidates = []
    if len(results) == 0:
        candidates = find_documents_by_fuzzy_title(clean_doc_id, table_name=table_name)
        if candidates:
            best_match = candidates[0]
            clean_doc_id = best_match["doc_id"]
            clean_sql_id = clean_doc_id.replace("'", "''")
            results = table.search().where(f"doc_id = '{clean_sql_id}'").limit(10000).to_arrow()
    
    if len(results) == 0:
        stats = get_rag_stats(table_name=table_name)
        avail = [f"- '{d['title']}' [doc_id: {d['id']}]" for d in stats.get("documents", [])[:10]]
        return {
            "success": False,
            "error": f"No se encontró ningún documento con ID o título que coincida con '{clean_doc_id}'.\n\nDocumentos disponibles en la biblioteca:\n" + "\n".join(avail),
            "doc_id": clean_doc_id
        }
        
    actual_doc_id = results["doc_id"][0].as_py() if "doc_id" in results.schema.names else clean_doc_id
    doc_title = results["doc_title"][0].as_py() if "doc_title" in results.schema.names else "Documento"
    doc_topic = results["doc_topic"][0].as_py() if "doc_topic" in results.schema.names else "General"
    doc_author = results["doc_author"][0].as_py() if "doc_author" in results.schema.names else "Desconocido"
    total_chunks = len(results)

    ids = results["id"].to_pylist() if "id" in results.schema.names else []
    sections = results["section_path"].to_pylist() if "section_path" in results.schema.names else []
    contents = results["content"].to_pylist() if "content" in results.schema.names else []
    chunk_tokens = results["chunk_tokens"].to_pylist() if "chunk_tokens" in results.schema.names else [len(c)//4 for c in contents]
    
    raw_doc_tokens = results["total_doc_tokens"][0].as_py() if "total_doc_tokens" in results.schema.names else None
    if raw_doc_tokens and raw_doc_tokens > 0:
        total_doc_tokens = int(raw_doc_tokens)
    else:
        total_doc_tokens = sum(tok if (tok and tok > 0) else max(1, len(c)//4) for tok, c in zip(chunk_tokens, contents))

    sorted_items = sorted(zip(ids, sections, contents, chunk_tokens), key=lambda x: x[0])

    alt_notice = ""
    if candidates and len(candidates) > 1:
        other_matches = [f"'{c['title']}' (doc_id: {c['doc_id']})" for c in candidates[1:4]]
        alt_notice = f"💡 *Nota de Búsqueda:* Se seleccionó '{doc_title}'. Otras coincidencias posibles: {', '.join(other_matches)}\n\n"

    # =========================================================================
    # FRENO DE MANO: PROTECCIÓN DE OBRAS EXTENSAS SIN SECCIÓN ACOTADA
    # =========================================================================
    clean_sec_check = (seccion or "").strip().lower()
    is_generic_or_missing_sec = (not seccion or clean_sec_check in ("sección general", "seccion general", "general"))
    if is_generic_or_missing_sec and total_doc_tokens > 25000:
        return {
            "success": False,
            "error": (
                f"⚠️ AVISO DE SEGURIDAD (OBRA EXTENSA): '{doc_title}' contiene ~{total_doc_tokens:,} tokens ({total_chunks} fragmentos).\n\n"
                f"Para proteger tu ventana de contexto y evitar desbordamiento de memoria, NO está permitido volcar esta obra completa o secciones masivas a ciegas.\n\n"
                f"💡 Guía de navegación: Para acotar la lectura de esta obra extensa sin desbordar el contexto, invoca 'obtener_estructura_documento(doc_id=\"{actual_doc_id}\")' para identificar el capítulo o artículo puntual que buscas, "
                f"o utiliza 'buscar_en_base_de_conocimiento(consulta=\"...\")' para recuperar directamente los fragmentos pertinentes."
            ),
            "doc_id": actual_doc_id,
            "total_doc_tokens": total_doc_tokens
        }

    # =========================================================================
    # CASO 1: BÚSQUEDA FOCALIZADA POR SECCIÓN O CAPÍTULO
    # =========================================================================
    if seccion and seccion.strip():
        clean_sec_req = seccion.strip()
        matched_items = []
        for ch_id, sec, cont, tok_cnt in sorted_items:
            if match_section_query(clean_sec_req, sec):
                matched_items.append((ch_id, sec, cont, tok_cnt))

        # Fallback tolerante si no hubo coincidencia por límites
        if not matched_items:
            req_sec_norm = normalize_text(clean_sec_req)
            for ch_id, sec, cont, tok_cnt in sorted_items:
                s_norm = normalize_text(sec)
                if req_sec_norm in s_norm or s_norm in req_sec_norm:
                    matched_items.append((ch_id, sec, cont, tok_cnt))
                
        if not matched_items:
            unique_secs = []
            for _, s, _, _ in sorted_items:
                if s and s not in unique_secs:
                    unique_secs.append(s)
            avail_secs = "\n".join([f"- {s}" for s in unique_secs[:15]])
            return {
                "success": False,
                "error": f"No se encontró la sección '{seccion}' en el documento '{doc_title}'.\n\nSecciones principales disponibles:\n{avail_secs}\n\n💡 Tip: Usa obtener_estructura_documento(doc_id=\"{actual_doc_id}\") para ver el índice completo.",
                "doc_id": actual_doc_id
            }

        sec_tokens = sum(t_c if (t_c and t_c > 0) else max(1, len(c) // 4) for _, _, c, t_c in matched_items)
        sec_name = matched_items[0][1]

        if sec_tokens <= effective_token_threshold:
            body_parts = []
            current_sec = None
            for _, s, cont, _ in matched_items:
                if s != current_sec:
                    current_sec = s
                    body_parts.append(f"\n\n### {s}\n")
                body_parts.append(cont)
            slice_text = "\n\n".join(body_parts).strip()
            if len(slice_text) > MAX_SAFE_TOOL_TOKENS * 4:
                slice_text = slice_text[:MAX_SAFE_TOOL_TOKENS * 4] + f"\n\n... [Aviso: Fragmento extenso acotado preventivamente a ~{MAX_SAFE_TOOL_TOKENS:,} tokens para proteger la ventana de contexto de la IA. Si necesitas una subsección específica, indícala en el parámetro 'seccion']."
            header = (
                f"# {doc_title} — Sección: \"{sec_name}\"\n"
                f"**ID:** {actual_doc_id} | **Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens Sección:** ~{sec_tokens:,} ({len(matched_items)} fragmentos) | **Total Obra:** ~{total_doc_tokens:,} tokens\n"
                f"**Modo de Recuperación:** Sección Focalizada Verificada desde LanceDB\n\n"
                f"{alt_notice}"
                f"---\n\n"
            )
            return {
                "success": True,
                "doc_id": actual_doc_id,
                "titulo": doc_title,
                "tema": doc_topic,
                "autor": doc_author,
                "seccion_solicitada": seccion,
                "seccion_nombre": sec_name,
                "total_chunks": total_chunks,
                "total_doc_tokens": total_doc_tokens,
                "tokens_en_esta_parte": sec_tokens,
                "chunks_en_esta_parte": len(matched_items),
                "modo": "seccion_focalizada",
                "parte_actual": 1,
                "total_partes": 1,
                "content": header + slice_text
            }
        else:
            partes_chunks = _partition_chunks_dynamically(matched_items, effective_token_threshold)
            total_partes = max(1, len(partes_chunks))
            parte = max(1, min(parte, total_partes))
            selected_slice, part_tokens = partes_chunks[parte - 1]
            body_parts = []
            current_sec = None
            for _, s, cont, _ in selected_slice:
                if s != current_sec:
                    current_sec = s
                    body_parts.append(f"\n\n### {s}\n")
                body_parts.append(cont)
            slice_text = "\n\n".join(body_parts).strip()
            if len(slice_text) > MAX_SAFE_TOOL_TOKENS * 4:
                slice_text = slice_text[:MAX_SAFE_TOOL_TOKENS * 4] + f"\n\n... [Aviso: Fragmento extenso acotado preventivamente a ~{MAX_SAFE_TOOL_TOKENS:,} tokens para proteger la ventana de contexto de la IA. Si necesitas una subsección específica, indícala en el parámetro 'seccion']."
            next_hint = f" (Para leer la siguiente parte de esta sección use parte={parte+1})" if parte < total_partes else " (Fin de la sección)"
            header = (
                f"# {doc_title} — Sección: \"{sec_name}\" (Parte {parte} de {total_partes})\n"
                f"**ID:** {actual_doc_id} | **Tokens en esta parte:** ~{part_tokens:,} ({len(selected_slice)} fragmentos) | **Total Sección:** ~{sec_tokens:,} tokens\n"
                f"**Aviso:** Sección extensa dividida con límites limpios de tolerancia.{next_hint}\n\n"
                f"---\n\n"
            )
            return {
                "success": True,
                "doc_id": actual_doc_id,
                "titulo": doc_title,
                "tema": doc_topic,
                "autor": doc_author,
                "seccion_solicitada": seccion,
                "seccion_nombre": sec_name,
                "total_chunks": total_chunks,
                "total_doc_tokens": total_doc_tokens,
                "tokens_en_esta_parte": part_tokens,
                "chunks_en_esta_parte": len(selected_slice),
                "modo": "seccion_paginada",
                "parte_actual": parte,
                "total_partes": total_partes,
                "content": header + slice_text
            }

    # =========================================================================
    # CASO 2: DOCUMENTO COMPLETO (< 60.000 tokens) -> 1:1 TECCAM PDF O LANCEDB
    # =========================================================================
    if total_doc_tokens <= effective_token_threshold:
        raw_detail = fetch_teccam_document_raw(actual_doc_id)
        if raw_detail and raw_detail.get("texto", "").strip():
            raw_text = raw_detail.get("texto", "").strip()
            header = (
                f"# {doc_title}\n"
                f"**ID:** {actual_doc_id} | **Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens:** ~{total_doc_tokens:,} ({total_chunks} fragmentos)\n"
                f"**Modo de Recuperación:** Documento Íntegro Oficial (Fidelidad 100% desde Teccam PDF)\n\n"
                f"{alt_notice}"
                f"---\n\n"
            )
            return {
                "success": True,
                "doc_id": actual_doc_id,
                "titulo": doc_title,
                "tema": doc_topic,
                "autor": doc_author,
                "total_chunks": total_chunks,
                "total_doc_tokens": total_doc_tokens,
                "tokens_en_esta_parte": total_doc_tokens,
                "modo": "completo_directo",
                "parte_actual": 1,
                "total_partes": 1,
                "content": header + raw_text
            }

    # =========================================================================
    # CASO 3: OBRAS MASIVAS (> 60.000 tokens) CON TOLERANCIA DINÁMICA (±5%-8%)
    # =========================================================================
    partes_chunks = _partition_chunks_dynamically(sorted_items, effective_token_threshold)
    total_partes = max(1, len(partes_chunks))
    parte = max(1, min(parte, total_partes))
    selected_slice, part_tokens = partes_chunks[parte - 1]

    body_parts = []
    current_sec = None
    for _, sec, cont, _ in selected_slice:
        if sec != current_sec:
            current_sec = sec
            body_parts.append(f"\n\n### {sec}\n")
        body_parts.append(cont)
    slice_text = "\n\n".join(body_parts).strip()

    if total_partes == 1:
        modo_str = "completo_lancedb"
        header = (
            f"# {doc_title}\n"
            f"**Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens:** ~{part_tokens:,} ({len(selected_slice)} fragmentos)\n"
            f"**Modo de Recuperación:** Documento Completo Reconstruido desde LanceDB\n\n"
            f"---\n\n"
        )
    else:
        modo_str = "paginado_jerarquico"
        next_hint = f" (Para leer la siguiente parte use parte={parte+1})" if parte < total_partes else " (Fin del documento)"
        header = (
            f"# {doc_title} (Parte {parte} de {total_partes})\n"
            f"**Tema:** {doc_topic} | **Autor:** {doc_author} | **Tokens en esta parte:** ~{part_tokens:,} ({len(selected_slice)} fragmentos) | **Total Obra:** ~{total_doc_tokens:,} tokens ({total_chunks} fragmentos)\n"
            f"**Aviso de Paginación Jerárquica:** Cortes alineados a límites naturales de capítulos con tolerancia dinámica (±5%-8%).{next_hint}\n"
            f"💡 **Tip:** Puedes consultar el mapa general con `obtener_estructura_documento(doc_id=\"{actual_doc_id}\")` o solicitar una sección directa.\n\n"
            f"---\n\n"
        )

    return {
        "success": True,
        "doc_id": actual_doc_id,
        "titulo": doc_title,
        "tema": doc_topic,
        "autor": doc_author,
        "total_chunks": total_chunks,
        "total_doc_tokens": total_doc_tokens,
        "tokens_en_esta_parte": part_tokens,
        "chunks_en_esta_parte": len(selected_slice),
        "modo": modo_str,
        "parte_actual": parte,
        "total_partes": total_partes,
        "content": header + slice_text
    }


def get_library_index(
    solo_vigentes: bool = False,
    tema: Optional[str] = None,
    table_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Genera un índice jerárquico macro de la biblioteca de conocimiento (Mapa Ontológico Global).
    
    Permite que modelos compactos (ej. 12B) o usuarios comprendan de inmediato la estructura completa
    de las obras disponibles, organizadas por dominios, con su estado de vigencia, ID y volumen de tokens.
    """
    table = get_table(table_name)
    if table is None or len(table) == 0:
        return {
            "success": False,
            "error": "Base vectorial LanceDB no inicializada o vacía.",
            "total_documents": 0,
            "domains": {},
            "content": "⚠️ La base de conocimiento de Teccam no tiene documentos indexados actualmente."
        }

    try:
        df = table.to_arrow()
        names = df.schema.names
        
        d_ids = df["doc_id"].to_pylist() if "doc_id" in names else []
        d_titles = df["doc_title"].to_pylist() if "doc_title" in names else []
        d_topics = df["doc_topic"].to_pylist() if "doc_topic" in names else []
        d_authors = df["doc_author"].to_pylist() if "doc_author" in names else ["Desconocido"] * len(d_ids)
        d_tokens = df["total_doc_tokens"].to_pylist() if "total_doc_tokens" in names else [0] * len(d_ids)
        d_vigs = df["doc_vigencia"].to_pylist() if "doc_vigencia" in names else ["NA (no aplica)"] * len(d_ids)
        d_fpubs = df["doc_fecha_publicacion"].to_pylist() if "doc_fecha_publicacion" in names else [""] * len(d_ids)
        
        docs_map = {}
        for d_id, d_t, d_top, d_auth, d_tok, d_v, d_fp in zip(d_ids, d_titles, d_topics, d_authors, d_tokens, d_vigs, d_fpubs):
            if d_id not in docs_map:
                docs_map[d_id] = {
                    "id": d_id,
                    "title": d_t,
                    "topic": d_top or "General",
                    "author": d_auth or "Desconocido",
                    "total_tokens": d_tok or 0,
                    "vigencia": d_v or "NA (no aplica)",
                    "fecha_publicacion": d_fp or "",
                    "chunks_count": 0
                }
            docs_map[d_id]["chunks_count"] += 1

        # Filtrar si se solicitó
        filtered_docs = list(docs_map.values())
        if solo_vigentes:
            filtered_docs = [d for d in filtered_docs if d["vigencia"] == "vigente"]
        if tema and tema.strip():
            # Separar por comas, barras, guiones o espacios para búsqueda tolerante (ej: 'Filosofia/Etica')
            clean_terms = [
                re.sub(r'[^a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]', '', t.lower())
                for t in re.split(r'[/,|+& -]+', tema.strip())
                if t.strip()
            ]
            clean_terms = [t for t in clean_terms if len(t) >= 3]
            if clean_terms:
                filtered_docs = [
                    d for d in filtered_docs
                    if any(term in d["topic"].lower() for term in clean_terms)
                ]

        # Agrupar por Dominio / Tema
        domains = {}
        for d in filtered_docs:
            top = d["topic"]
            if top not in domains:
                domains[top] = []
            domains[top].append(d)

        # Ordenar documentos dentro de cada dominio por vigencia (vigente primero) y título
        vig_priority = {
            "vigente": 1,
            "parcialmente-vigente": 2,
            "en-proyecto": 3,
            "NA (no aplica)": 4,
            "derogado": 5
        }
        for top in domains:
            domains[top].sort(key=lambda x: (vig_priority.get(x["vigencia"], 99), x["title"]))

        # Construir representación Markdown para el LLM y Usuario
        total_docs = len(filtered_docs)
        total_chunks = sum(d["chunks_count"] for d in filtered_docs)
        total_tokens = sum(d["total_tokens"] for d in filtered_docs)
        
        md_lines = [
            "# 🗺️ Mapa Ontológico Global de la Biblioteca (Base RAG Teccam)",
            f"**Obras Disponibles:** {total_docs} | **Dominios:** {len(domains)} | **Total Fragmentos:** {total_chunks:,} | **Tokens Acumulados:** ~{total_tokens:,}\n",
            "A continuación se detalla el catálogo temático jerarquizado para orientar consultas y navegación precisa:\n"
        ]
        
        for dom, d_list in sorted(domains.items()):
            icon = "⚖️" if "derecho" in dom.lower() else "🛠️" if "procedimiento" in dom.lower() or "soporte" in dom.lower() else "🧠" if "filosof" in dom.lower() or "etica" in dom.lower() else "💻" if "patron" in dom.lower() or "ingenier" in dom.lower() else "📚"
            md_lines.append(f"### {icon} Dominio: {dom} ({len(d_list)} obras)")
            for d in d_list:
                vig_str = d["vigencia"]
                vig_badge = f"**[{vig_str.upper()}]**" if vig_str != "NA (no aplica)" else "[N/A]"
                fpub_str = f" | B.O.: {d['fecha_publicacion']}" if d.get("fecha_publicacion") else ""
                tokens_str = f"~{d['total_tokens']:,} tokens" if d.get("total_tokens") else f"{d['chunks_count']} chunks"
                
                md_lines.append(
                    f"- 📖 **{d['title']}** {vig_badge} [doc_id: `{d['id']}`] ({tokens_str}{fpub_str})\n"
                    f"  * Explorar índice de capítulos: `obtener_estructura_documento(doc_id=\"{d['id']}\")`\n"
                    f"  * Lectura directa: `leer_documento_completo(doc_id=\"{d['id']}\")`"
                )
            md_lines.append("")

        md_lines.append(
            "---\n"
            "💡 **Guía de Uso para el LLM:**\n"
            "1. Para ubicar temas específicos dentro de una ley o libro extenso, invoca primero `obtener_estructura_documento(doc_id)`. Nunca adivines la sección.\n"
            "2. Para leer capítulos o artículos específicos, invoca `leer_documento_completo(doc_id, seccion=\"<nombre>\")`.\n"
            "3. En consultas jurídicas, prioriza fuentes con estado `[VIGENTE]`. Si citas normas `[DEROGADO]`, adviértelo explícitamente al usuario.\n"
            "4. Este índice contiene únicamente títulos y metadatos orientativos. Si vas a describir, listar o fundamentar el contenido de estas normas, está ESTRICTAMENTE PROHIBIDO inferir o asumir su materia por el título: es OBLIGATORIO invocar `leer_documento_completo(doc_id)` para consultar el texto oficial antes de responder."
        )

        return {
            "success": True,
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_tokens": total_tokens,
            "domains_count": len(domains),
            "domains": domains,
            "content": "\n".join(md_lines)
        }
    except Exception as e:
        print(f"⚠️ [RAG Engine] Error generando índice de biblioteca: {e}", file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "content": f"Error al generar índice de biblioteca: {str(e)}"
        }


__all__ = [
    "fetch_teccam_document_raw",
    "get_document_structure",
    "_partition_chunks_dynamically",
    "get_document_full_content",
    "get_library_index"
]
