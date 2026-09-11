"""
rag.search - Búsqueda híbrida (Vectorial 1024D + FTS BM25), boosting normativo, expansión contigua y formateo LLM.
"""

import re
import sys
import time
from typing import List, Dict, Any, Optional
from .db import get_table
from .embeddings import generate_embedding
from .settings import get_rag_settings
from .matching import normalize_text


def search_knowledge_base(
    query: str,
    tema: Optional[Any] = None,
    temas: Optional[List[str]] = None,
    documento_id: Optional[str] = None,
    doc_id: Optional[str] = None,
    vigencia: Optional[str] = None,
    solo_vigentes: bool = False,
    top_k: int = 5,
    min_score: float = 0.25,
    table_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Ejecuta una búsqueda híbrida (Vectorial 1024D + FTS BM25) sobre LanceDB (por defecto o específica por empresa).
    
    Args:
        query: Consulta del usuario en lenguaje natural o palabras clave.
        tema: Filtro opcional por tema/dominio (string o lista de strings).
        temas: Filtro opcional por lista de dominios múltiples.
        documento_id: Filtro opcional por ID de libro específico.
        doc_id: Alias para documento_id (para compatibilidad con herramientas del LLM).
        vigencia: Filtro opcional por estado de vigencia ('vigente', 'derogado', etc.).
        solo_vigentes: Si es True, restringe exclusivamente a normas con doc_vigencia = 'vigente'.
        top_k: Cantidad de fragmentos más relevantes a retornar.
        min_score: Umbral mínimo de similitud/relevancia.
        table_name: Nombre opcional de la tabla/base de la empresa.
        
    Returns:
        Lista de diccionarios con fragmentos, metadatos, citas y puntuación.
    """
    t0 = time.time()
    table = get_table(table_name)
    if table is None or len(table) == 0:
        return []

    query_str = query.strip()
    if not query_str:
        return []

    # 1. Generar vector para la consulta del usuario
    query_vector = generate_embedding(query_str)

    # 2. Determinar dominios/temas a filtrar
    topics_to_filter = []
    if temas and isinstance(temas, list):
        topics_to_filter = [t.strip() for t in temas if t and isinstance(t, str) and t.strip()]
    elif tema:
        if isinstance(tema, list):
            topics_to_filter = [t.strip() for t in tema if t and isinstance(t, str) and t.strip()]
        elif isinstance(tema, str) and tema.strip():
            if "," in tema:
                topics_to_filter = [t.strip() for t in tema.split(",") if t.strip()]
            else:
                topics_to_filter = [tema.strip()]
    else:
        # Si no se pasó filtro explícito, aplicar los dominios activos globales si existen
        global_settings = get_rag_settings()
        topics_to_filter = global_settings.get("active_topics", [])

    # 3. Construir filtro SQL / pre-filter si aplica
    filter_clauses = []
    topic_conditions = []
    if topics_to_filter:
        for t in topics_to_filter:
            if t and t.strip():
                clean_t = t.strip().replace("'", "''")
                norm_t = normalize_text(clean_t)
                topic_conditions.append(
                    f"(lower(doc_topic) LIKE '%{clean_t.lower()}%' OR "
                    f"lower(doc_title) LIKE '%{clean_t.lower()}%' OR "
                    f"lower(doc_title) LIKE '%{norm_t}%')"
                )
        if len(topic_conditions) == 1:
            filter_clauses.append(topic_conditions[0])
        elif len(topic_conditions) > 1:
            filter_clauses.append(f"({' OR '.join(topic_conditions)})")

    effective_doc_id = (documento_id or doc_id or "").strip()
    if effective_doc_id:
        clean_doc_id = effective_doc_id.replace("'", "''")
        filter_clauses.append(f"doc_id = '{clean_doc_id}'")

    if solo_vigentes:
        filter_clauses.append("doc_vigencia = 'vigente'")
    elif vigencia and vigencia.strip():
        clean_vig = vigencia.strip().replace("'", "''")
        filter_clauses.append(f"doc_vigencia = '{clean_vig}'")
        
    filter_expr = " AND ".join(filter_clauses) if filter_clauses else None

    # Detectar si la consulta busca un artículo normativo específico para boosting (soporta sufijos bis/ter)
    art_match = re.search(
        r"(?:art[ií]culo|art\.)\s*(\d+[°º]?(?:\s*(?:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies))?)",
        query_str,
        re.IGNORECASE
    )
    target_art_num = art_match.group(1).strip() if art_match else None

    cand_limit = max(80, top_k * 10)
    all_candidates = {}
    
    # A) Búsqueda vectorial semántica (1024D)
    try:
        vec_builder = table.search(query_vector, query_type="vector")
        if filter_expr:
            vec_builder = vec_builder.where(filter_expr)
        vec_results = vec_builder.limit(cand_limit).to_list()
        
        for item in vec_results:
            d_id = item.get("id")
            dist = item.get("_distance", 1.0)
            similarity = max(0.0, 1.0 - (dist / 2.0))
            all_candidates[d_id] = {
                "item": item,
                "vec_sim": similarity,
                "fts_score": 0.0,
                "dist": dist
            }
    except Exception as ve:
        print(f"⚠️ [RAG Engine] Error en búsqueda vectorial: {ve}", file=sys.stderr)

    # B) Búsqueda de texto completo (BM25 / FTS)
    try:
        fts_builder = table.search(query_str, query_type="fts")
        if filter_expr:
            fts_builder = fts_builder.where(filter_expr)
        fts_results = fts_builder.limit(cand_limit).to_list()
        
        max_fts = max([r.get("_score", 0.0) for r in fts_results]) if fts_results else 1.0
        if max_fts <= 0:
            max_fts = 1.0
            
        for item in fts_results:
            d_id = item.get("id")
            raw_score = item.get("_score", 0.0)
            norm_fts = raw_score / max_fts
            
            if d_id in all_candidates:
                all_candidates[d_id]["fts_score"] = norm_fts
            else:
                all_candidates[d_id] = {
                    "item": item,
                    "vec_sim": 0.65, # Baseline de similitud semántica para matches léxicos
                    "fts_score": norm_fts,
                    "dist": 0.70
                }
    except Exception:
        pass

    # Fallback de seguridad: si un filtro temático restrictivo devolvió 0 candidatos
    # (ej: el LLM pasó un nombre de subdisciplina o ley que no coincide con doc_topic ni doc_title),
    # reintentar búsqueda vectorial sin la cláusula temática para no dejar sin respuesta al usuario.
    if not all_candidates and topics_to_filter:
        non_topic_clauses = [c for c in filter_clauses if c not in topic_conditions and not any(tc in c for tc in topic_conditions)]
        fallback_expr = " AND ".join(non_topic_clauses) if non_topic_clauses else None
        try:
            vec_builder = table.search(query_vector, query_type="vector")
            if fallback_expr:
                vec_builder = vec_builder.where(fallback_expr)
            for item in vec_builder.limit(top_k * 5).to_list():
                d_id = item.get("id")
                dist = item.get("_distance", 1.0)
                all_candidates[d_id] = {
                    "item": item,
                    "vec_sim": max(0.0, 1.0 - (dist / 2.0)),
                    "fts_score": 0.0,
                    "dist": dist
                }
        except Exception:
            pass

    results = []
    for d_id, data in all_candidates.items():
        item = data["item"]
        v_sim = data["vec_sim"]
        f_sim = data["fts_score"]
        
        # Fusión híbrida ponderada
        if f_sim > 0:
            final_sim = (v_sim * 0.45) + (f_sim * 0.55)
        else:
            final_sim = v_sim * 0.85

        # Si la consulta busca un artículo específico, aplicar boosting al fragmento exacto
        if target_art_num:
            sec_p = item.get("section_path", "") or ""
            cnt = item.get("content", "") or ""
            clean_target = re.escape(target_art_num)
            has_suffix = bool(re.search(r"\b(?:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies)\b", target_art_num, re.IGNORECASE))
            if not has_suffix:
                # Si busca '14', no debe matchear '14 bis'
                art_regex = rf"(?:art[ií]culo|art\.)\s*{clean_target}(?![°º]?\s*(?:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies))\b"
            else:
                # Si busca '14 bis', matchea '14 bis'
                art_regex = rf"(?:art[ií]culo|art\.)\s*{clean_target}\b"

            if re.search(art_regex, sec_p, re.IGNORECASE):
                final_sim += 0.35 # Fuerte impulso si la sección es el artículo
            elif re.search(art_regex, cnt[:150], re.IGNORECASE):
                final_sim += 0.25 # Impulso si el contenido comienza con el artículo

        # Boost para disposiciones generales cuando se busca definición o concepto general
        is_definitional = bool(re.search(r"\b(?:definici[oó]n|concepto|qu[eé]\s+es|noci[oó]n)\b", query_str, re.IGNORECASE))
        if is_definitional:
            sec_p = item.get("section_path", "") or ""
            if re.search(r"\b(?:disposiciones\s+generales|disposici[oó]n\s+general|parte\s+general|t[ií]tulo\s+preliminar)\b", sec_p, re.IGNORECASE):
                final_sim += 0.06
            
        if final_sim >= min_score or len(results) < top_k:
            results.append({
                "id": item.get("id"),
                "doc_id": item.get("doc_id"),
                "doc_title": item.get("doc_title"),
                "doc_author": item.get("doc_author"),
                "doc_topic": item.get("doc_topic"),
                "doc_vigencia": item.get("doc_vigencia") or "NA (no aplica)",
                "doc_fecha_publicacion": item.get("doc_fecha_publicacion") or "",
                "section_path": item.get("section_path"),
                "chunk_index": item.get("chunk_index"),
                "chunk_tokens": item.get("chunk_tokens"),
                "total_chunks": item.get("total_chunks"),
                "total_doc_tokens": item.get("total_doc_tokens"),
                "content": item.get("content"),
                "enriched_text": item.get("text"),
                "similarity": round(final_sim, 4),
                "distance": round(data["dist"], 4)
            })

    # Ordenar por score híbrido preliminar
    preliminary_results = sorted(results, key=lambda x: x["similarity"], reverse=True)[:top_k]

    # Expansión de Chunks Adyacentes (Anti-Truncamiento / Ley 4):
    # Si un fragmento es breve (< 350 tokens) o forma parte de un artículo extenso fraccionado,
    # se expande con los fragmentos contiguos de la misma sección para no generar recortes engañosos.
    expanded_results = []
    consumed_chunk_keys = set()

    for r in preliminary_results:
        d_id = r.get("doc_id")
        c_idx = r.get("chunk_index")
        chunk_key = (d_id, c_idx)
        if chunk_key in consumed_chunk_keys:
            continue

        s_path = r.get("section_path")
        total_c = r.get("total_chunks") or 0
        curr_tokens = r.get("chunk_tokens") or 0
        curr_c_idx = c_idx

        expansions = 0
        while curr_c_idx is not None and d_id and s_path and (curr_c_idx + 1) < total_c and expansions < 2:
            try:
                next_records = table.search().where(f"doc_id = '{d_id}' AND chunk_index = {curr_c_idx + 1}").limit(1).to_pandas()
                if next_records.empty:
                    break
                next_row = next_records.iloc[0]
                if next_row.get("section_path") != s_path:
                    break
                next_cnt = (next_row.get("content") or "").strip()
                next_toks = int(next_row.get("chunk_tokens") or max(1, len(next_cnt) // 4))
                if curr_tokens + next_toks > 650:
                    break

                base_cnt = r.get("content", "").strip()
                overlap_match = False
                for ol_len in range(min(120, len(base_cnt)), 20, -1):
                    suffix = base_cnt[-ol_len:].strip()
                    if next_cnt.startswith(suffix):
                        stitched = base_cnt + " " + next_cnt[len(suffix):].lstrip()
                        overlap_match = True
                        break
                if not overlap_match:
                    stitched = base_cnt + "\n" + next_cnt

                r["content"] = stitched
                curr_tokens += next_toks
                r["chunk_tokens"] = curr_tokens
                curr_c_idx += 1
                consumed_chunk_keys.add((d_id, curr_c_idx))
                expansions += 1
            except Exception:
                break

        expanded_results.append(r)

    final_results = expanded_results
    dur_ms = (time.time() - t0) * 1000
    print(f"🔍 [RAG Search] Consulta: '{query_str[:40]}...' | {len(final_results)} resultados en {dur_ms:.2f} ms")
    return final_results


def format_rag_context_for_llm(results: List[Dict[str, Any]]) -> str:
    """Formatea los resultados de búsqueda en un bloque de contexto claro y estructurado con citas, vigencia y doc_id para el LLM."""
    if not results:
        return "No se encontraron fragmentos relevantes en la base de conocimiento de Teccam."
        
    snippets = []
    for idx, item in enumerate(results, 1):
        doc_title = item.get("doc_title", "Documento sin título")
        doc_id = item.get("doc_id", "")
        doc_topic = item.get("doc_topic", "General")
        doc_vigencia = item.get("doc_vigencia") or "NA (no aplica)"
        doc_fecha_pub = item.get("doc_fecha_publicacion") or ""
        section = item.get("section_path", "Sección Principal")
        author = item.get("doc_author", "Desconocido")
        content = item.get("content", "").strip()
        sim_pct = int(item.get("similarity", 0) * 100)
        c_tokens = item.get("chunk_tokens")
        tot_tokens = item.get("total_doc_tokens") or 0
        tokens_tag = f" | Tokens: ~{c_tokens}" if c_tokens else ""
        
        # Tags de metadata de vigencia y publicación
        vig_tag = f" | Vigencia: {doc_vigencia.upper()}" if doc_vigencia and doc_vigencia != "NA (no aplica)" else ""
        pub_tag = f" | B.O.: {doc_fecha_pub}" if doc_fecha_pub and doc_fecha_pub.strip() else ""

        # Advertencia proactiva para el LLM en caso de normas no vigentes
        if doc_vigencia == "derogado":
            vig_alert = "⚠️ [Aviso Crítico de Vigencia]: Esta norma se encuentra DEROGADA. Citarla exclusivamente con fines comparativos o doctrinales, no como derecho positivo aplicable.\n"
        elif doc_vigencia == "parcialmente-vigente":
            vig_alert = "⚠️ [Aviso de Vigencia]: Esta norma posee reformas o vigencia PARCIAL. Verificar si los artículos citados continúan vigentes.\n"
        elif doc_vigencia == "en-proyecto":
            vig_alert = "ℹ️ [Aviso de Estado]: Este documento es un ANTEPROYECTO / PROYECTO de ley en trámite parlamentario, no constituye norma sancionada.\n"
        else:
            vig_alert = ""
        
        # Si el documento supera los 30.000 tokens o 100 fragmentos, incluir guía de GPS Documental y lectura por sección
        if tot_tokens > 30000 or item.get("total_chunks", 0) > 100:
            clean_sec_hint = section.split(">")[-1].strip() if ">" in section else section
            action_hint = (
                f"💡 [Acción Disponible (Obra Extensa ~{tot_tokens:,} tokens)]:\n"
                f"   - Para explorar el índice/GPS de capítulos usa: obtener_estructura_documento(doc_id=\"{doc_id}\")\n"
                f"   - Para leer una sección o libro específico usa: leer_documento_completo(doc_id=\"{doc_id}\", seccion=\"{clean_sec_hint}\")"
            )
        else:
            action_hint = f"💡 [Acción Disponible: Para leer este documento completo o hacer una síntesis integral usa: leer_documento_completo(doc_id=\"{doc_id}\")]"
        
        snippets.append(
            f"--- FUENTE [{idx}]: \"{doc_title}\" [doc_id: {doc_id}] (Tema: {doc_topic}{vig_tag}{pub_tag} | Sección: {section} | Autor: {author}{tokens_tag} | Coincidencia: {sim_pct}%) ---\n"
            f"{vig_alert}"
            f"{action_hint}\n"
            f"{content}"
        )
        
    return "\n\n".join(snippets)


__all__ = [
    "search_knowledge_base",
    "format_rag_context_for_llm"
]
