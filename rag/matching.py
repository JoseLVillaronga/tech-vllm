"""
rag.matching - Normalización de texto, límites de palabra seguros (Anti-Colisiones Romanas) y búsqueda difusa.
"""

import re
import unicodedata
from typing import List, Dict, Any, Optional
from .db import get_table


def normalize_text(text: str) -> str:
    """Elimina acentos, diacríticos y normaliza a minúsculas para comparaciones tolerantes."""
    if not text:
        return ""
    text = str(text).lower().strip()
    nfkd = unicodedata.normalize('NFKD', text)
    cleaned = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ' '.join(cleaned.split())


def build_boundary_regex(phrase: str) -> str:
    """Construye un patrón regex con límites de palabra seguros al inicio y al final si son alfanuméricos."""
    if not phrase:
        return ""
    words = [re.escape(w) for w in phrase.split()]
    inner = r"\s+".join(words)
    prefix = r"(?:\b|^)" if phrase[0].isalnum() else ""
    suffix = r"(?:\b|$)" if phrase[-1].isalnum() else ""
    return prefix + inner + suffix


def match_section_query(query: str, target: str) -> bool:
    """
    Comprueba si una consulta o filtro coincide semántica y estructuralmente con una ruta de sección.
    - Respeta límites de palabra para evitar colisiones de números romanos (ej: 'titulo i' dentro de 'titulo ii' o 'titulo ix').
    - Admite consultas jerárquicas compuestas (ej: 'Libro II Titulo I', 'Titulo I del Libro II', 'Libro II > Titulo I').
    - Tolera diferencias de acentos, mayúsculas y diacríticos.
    - Maneja abreviaturas normativas comunes ('art. 79' vs 'articulo 79').
    """
    if not query or not target:
        return False

    q_norm = normalize_text(query)
    t_norm = normalize_text(target)
    if not q_norm or not t_norm:
        return False

    # 1. Coincidencia completa con límites seguros
    full_pat = build_boundary_regex(q_norm)
    if re.search(full_pat, t_norm):
        return True

    # 2. Inverso: si el target (o su parte final) está contenido en la consulta
    target_pat = build_boundary_regex(t_norm)
    if re.search(target_pat, q_norm):
        return True

    # 3. Consultas compuestas estructuradas (ej: "Titulo I del Libro II", "Libro II Titulo I")
    raw_clauses = re.split(r"\s*(?:>|-|,|\bdel\b|\bde\s+la\b|\bde\s+los\b|\bde\b|\ben\s+el\b|\ben\b)\s*", q_norm)
    clauses = [c.strip() for c in raw_clauses if len(c.strip()) >= 2]
    
    if len(clauses) <= 1:
        struct_split = re.split(r"(?<=\S)\s+(?=(?:libro|titulo|capitulo|seccion|parte|articulo|art)\b)", q_norm)
        if len(struct_split) > 1:
            clauses = [c.strip() for c in struct_split if len(c.strip()) >= 2]

    if len(clauses) > 1:
        all_match = True
        for clause in clauses:
            c_pat = build_boundary_regex(clause)
            if not re.search(c_pat, t_norm):
                all_match = False
                break
        if all_match:
            return True

    # 4. Fallback tolerante para abreviaturas tipo "art. 79" vs "articulo 79"
    q_expanded = re.sub(r"\bart(?:\.|\b)\s*", "articulo ", q_norm)
    t_expanded = re.sub(r"\bart(?:\.|\b)\s*", "articulo ", t_norm)
    if q_expanded != q_norm or t_expanded != t_norm:
        exp_pat = build_boundary_regex(q_expanded)
        if re.search(exp_pat, t_expanded):
            return True

    return False


def find_documents_by_fuzzy_title(query: str, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Busca documentos en LanceDB que coincidan con la consulta por título, palabras clave o substring (estilo SQL LIKE %...%).
    Tolera diferencias de acentos, mayúsculas, signos de puntuación y orden de palabras.
    """
    table = get_table(table_name)
    if table is None or len(table) == 0:
        return []
        
    df = table.to_arrow()
    if "doc_title" not in df.schema.names or "doc_id" not in df.schema.names:
        return []
        
    titles = df["doc_title"].to_pylist()
    ids = df["doc_id"].to_pylist()
    topics = df["doc_topic"].to_pylist() if "doc_topic" in df.schema.names else ["General"] * len(ids)
    authors = df["doc_author"].to_pylist() if "doc_author" in df.schema.names else ["Desconocido"] * len(ids)
    
    unique_docs = {}
    for d_id, t, top, aut in zip(ids, titles, topics, authors):
        if d_id not in unique_docs:
            unique_docs[d_id] = {
                "doc_id": d_id,
                "title": t,
                "topic": top,
                "author": aut,
                "chunks_count": 0
            }
        unique_docs[d_id]["chunks_count"] += 1
        
    q_norm = normalize_text(query)
    q_words = set(w for w in q_norm.split() if len(w) > 2)
    
    candidates = []
    for d_id, doc in unique_docs.items():
        t_norm = normalize_text(doc["title"])
        t_words = set(w for w in t_norm.split() if len(w) > 2)
        
        score = 0.0
        # 1. Coincidencia exacta normalizada
        if q_norm == t_norm:
            score = 1.0
        # 2. Substring (LIKE %...%)
        elif q_norm in t_norm or t_norm in q_norm:
            score = 0.90
        # 3. Coincidencia por conjunto de palabras clave
        else:
            common = q_words.intersection(t_words)
            if common and (len(common) >= min(len(q_words), 2) or len(common) == len(q_words)):
                score = len(common) / max(len(q_words), len(t_words))
                
        if score >= 0.20:
            candidates.append({
                **doc,
                "score": round(score, 2)
            })
            
    return sorted(candidates, key=lambda x: x["score"], reverse=True)


__all__ = [
    "normalize_text",
    "build_boundary_regex",
    "match_section_query",
    "find_documents_by_fuzzy_title"
]
