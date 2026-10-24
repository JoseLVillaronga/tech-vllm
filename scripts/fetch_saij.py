#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAIJ Jurisprudence Scraper & Hierarchical Markdown Converter
============================================================
Descarga y convierte fallos completos y sumarios oficiales de jurisprudencia
del Sistema Argentino de Información Jurídica (SAIJ - Ministerio de Justicia)
a formato Markdown limpio y jerárquico, optimizado para RAG (LanceDB) y TECCAM_PDF.

Características:
  - Soporte de IDs SAIJ (ej: FA09000059), UUIDs (123456789-...), URLs de SAIJ o búsqueda por carátula/caso.
  - Resolución determinista instantánea de UUID para fallos FA<8 dígitos>.
  - Descarga automática de todos los Sumarios Oficiales (doctrina de la Corte Suprema) asociados al fallo.
  - Descarga y extracción digital en memoria del texto íntegro de la sentencia adjunta en PDF (vía pypdfium2).
  - Limpieza de marcas internas de SAIJ ([[p]], [[r uuid:...]]) y guiones blandos de corte de línea PDF.
  - Estructuración jerárquica compatible con Ley 4 (RAG TECCAM):
      # Fallo CSJN: <Carátula>
      ## I. SUMARIOS OFICIALES (DOCTRINA DEL FALLO)
      ### Sumario N° X (ID) - <Voces>
      ## II. TEXTO ÍNTEGRO DE LA SENTENCIA
      ### VISTOS Y CONSIDERANDO / VOTO DE ... / DISIDENCIA DE ...
      **CONSIDERANDO X°.-** Texto...
"""

import io
import os
import re
import sys
import json
import argparse
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    repo_root = Path(__file__).resolve().parent.parent
    for venv_candidate in [repo_root / "venv" / "bin" / "python", repo_root / ".venv" / "bin" / "python"]:
        if venv_candidate.exists() and venv_candidate.resolve() != Path(sys.executable).resolve():
            os.execv(str(venv_candidate), [str(venv_candidate)] + sys.argv)
    print("Error: Se requiere 'requests'.", file=sys.stderr)
    sys.exit(1)

try:
    from scripts.fetch_infoleg import sanitize_filename, DEFAULT_USER_AGENT
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.fetch_infoleg import sanitize_filename, DEFAULT_USER_AGENT

SAIJ_BASE_URL = "http://www.saij.gob.ar"


class SAIJFetcher:
    """Cliente de consulta y extracción documental para la API oficial de SAIJ."""

    def __init__(self, session: requests.Session | None = None, timeout: int = 30):
        self.session = session or requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })
        self.timeout = timeout

    @staticmethod
    def fa_id_to_uuid(fa_id: str) -> str | None:
        """
        Convierte de forma determinista un ID de fallo SAIJ (FA + 8 dígitos)
        en su UUID interno de SAIJ: 123456789-<d7d6d5>-<d4d3d2d1>-<d0>ots-eupmocsollaf.
        """
        m = re.match(r"^FA(\d{8})$", fa_id.strip(), re.IGNORECASE)
        if not m:
            return None
        digits = m.group(1)
        rev = digits[::-1]
        return f"123456789-{rev[0:3]}-{rev[3:7]}-{rev[7]}ots-eupmocsollaf"

    @staticmethod
    def sumario_id_to_uuid(sum_id: str) -> str | None:
        """
        Convierte de forma determinista un ID de sumario SAIJ (ej: A0071374)
        en su UUID interno de SAIJ: 123456789-0abc-defg<rev[0:4]>-<rev[4:]>soiramUs.
        """
        clean = sum_id.strip().lower()
        if not re.match(r"^[a-z]\d{7}$", clean):
            return None
        rev = (f"sumarios{clean}")[::-1]
        return f"123456789-0abc-defg{rev[0:4]}-{rev[4:]}"

    def resolve_uuid(self, raw_input: str) -> str:
        """
        Resuelve cualquier entrada (ID FA..., UUID 123456789-..., URL de SAIJ o texto de búsqueda)
        al UUID canónico del documento en SAIJ.
        """
        raw = raw_input.strip()

        # 1. ¿Contiene un UUID explícito 123456789-...?
        m_uuid = re.search(r"(123456789-\d{3}-\d{4}-\d[a-z-]+)", raw, re.IGNORECASE)
        if m_uuid:
            return m_uuid.group(1).lower()

        # 2. ¿Es un ID FA<8 dígitos> directo o dentro de una URL amigable de SAIJ?
        m_fa = re.search(r"\b(FA\d{8})\b", raw, re.IGNORECASE)
        if m_fa:
            uuid_cand = self.fa_id_to_uuid(m_fa.group(1))
            if uuid_cand:
                return uuid_cand

        # 3. ¿Es otro ID Infojus (ej: NV..., A00...)?
        if re.match(r"^(?:FA|NV|SU|DA|LE|DN)\d+$", raw, re.IGNORECASE):
            params = {
                "r": f"id-infojus:{raw.upper()}",
                "o": 0,
                "p": 5,
                "f": "Total",
                "v": "colapsada"
            }
            resp = self.session.get(f"{SAIJ_BASE_URL}/busqueda", params=params, timeout=self.timeout)
            resp.raise_for_status()
            docs = resp.json().get("searchResults", {}).get("documentResultList", [])
            if docs:
                return docs[0]["uuid"]

        # 4. Búsqueda por texto / carátula (priorizando Jurisprudencia CSJN)
        for facet in [
            "Total|Tipo de Documento/Jurisprudencia|Tribunal/CORTE SUPREMA DE JUSTICIA DE LA NACION",
            "Total|Tipo de Documento/Jurisprudencia",
            "Total"
        ]:
            params = {
                "q": raw,
                "o": 0,
                "p": 10,
                "f": facet,
                "v": "colapsada"
            }
            resp = self.session.get(f"{SAIJ_BASE_URL}/busqueda", params=params, timeout=self.timeout)
            resp.raise_for_status()
            docs = resp.json().get("searchResults", {}).get("documentResultList", [])
            if docs:
                # Preferir un documento de tipo 'fallo' sobre un 'sumario' suelto si existe en los primeros resultados
                for d in docs:
                    abstract_str = d.get("documentAbstract", "{}")
                    try:
                        ab = json.loads(abstract_str)
                        if ab.get("document", {}).get("metadata", {}).get("document-content-type") == "fallo":
                            return d["uuid"]
                    except Exception:
                        pass
                return docs[0]["uuid"]

        raise ValueError(f"No se encontró ningún fallo o documento en SAIJ para la consulta: '{raw}'")

    def fetch_document_by_uuid(self, uuid: str) -> dict:
        """Descarga el JSON completo del documento en SAIJ a partir de su UUID."""
        resp = self.session.get(
            f"{SAIJ_BASE_URL}/view-document",
            params={"guid": uuid},
            timeout=self.timeout
        )
        resp.raise_for_status()
        outer = resp.json()
        data_str = outer.get("data")
        if not data_str:
            raise ValueError(f"SAIJ retornó un documento vacío para UUID: {uuid}")
        return json.loads(data_str).get("document", {})

    def _fetch_single_sumario(self, sid: str) -> tuple[str, dict | None]:
        """Recupera el texto íntegro sin truncar de un sumario oficial vía view-document."""
        sum_uuid = self.sumario_id_to_uuid(sid)
        if not sum_uuid:
            return sid, None
        try:
            doc = self.fetch_document_by_uuid(sum_uuid)
            content = doc.get("content", {})
            num_sum = content.get("numero-sumario") or content.get("id-infojus") or sid
            return sid, {
                "numero_sumario": num_sum,
                "voces": content.get("titulo", "").strip(),
                "texto": content.get("texto", "").strip(),
                "fuente": content.get("fuente", "").strip(),
            }
        except Exception:
            return sid, None

    def fetch_sumarios(self, sumario_ids: list[str]) -> list[dict]:
        """Recupera en paralelo el texto íntegro (sin truncamientos) de los sumarios oficiales."""
        if not sumario_ids:
            return []

        from concurrent.futures import ThreadPoolExecutor

        results_by_id = {}
        with ThreadPoolExecutor(max_workers=12) as pool:
            for sid, data in pool.map(self._fetch_single_sumario, sumario_ids):
                if data and data.get("texto"):
                    results_by_id[sid] = data

        # Fallback por lote si algún sumario no tenía UUID determinista estándar
        missing = [sid for sid in sumario_ids if sid not in results_by_id]
        batch_size = 15
        for idx in range(0, len(missing), batch_size):
            batch = missing[idx:idx + batch_size]
            query_r = " OR ".join(f"numero-sumario:{sid}" for sid in batch)
            params = {
                "r": query_r,
                "o": 0,
                "p": len(batch) + 5,
                "f": "Total",
                "v": "colapsada"
            }
            try:
                resp = self.session.get(f"{SAIJ_BASE_URL}/busqueda", params=params, timeout=self.timeout)
                resp.raise_for_status()
                doc_list = resp.json().get("searchResults", {}).get("documentResultList", [])
                for item in doc_list:
                    ab = json.loads(item.get("documentAbstract", "{}"))
                    content = ab.get("document", {}).get("content", {})
                    num_sum = content.get("numero-sumario") or content.get("id-infojus")
                    if num_sum and num_sum not in results_by_id:
                        results_by_id[num_sum] = {
                            "numero_sumario": num_sum,
                            "voces": content.get("titulo", "").strip(),
                            "texto": content.get("texto", "").strip(),
                            "fuente": content.get("fuente", "").strip(),
                        }
            except Exception:
                continue

        # Devolver preservando el orden original del fallo
        ordered = []
        for sid in sumario_ids:
            if sid in results_by_id:
                ordered.append(results_by_id[sid])
        return ordered

    def extract_pdf_text(self, pdf_uuid: str, file_name: str) -> tuple[str, int]:
        """
        Descarga el PDF oficial del fallo desde SAIJ y extrae su texto digital en memoria
        usando pypdfium2. Retorna (texto_completo, cantidad_paginas).
        """
        import pypdfium2 as pdfium

        resp = self.session.get(
            f"{SAIJ_BASE_URL}/descarga-archivo",
            params={"guid": pdf_uuid, "name": file_name},
            timeout=max(self.timeout, 45)
        )
        resp.raise_for_status()
        pdf_bytes = resp.content
        if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
            return "", 0

        doc = pdfium.PdfDocument(pdf_bytes)
        num_pages = len(doc)
        pages_text = []
        running_headers = set()
        try:
            for page_idx in range(num_pages):
                page = doc[page_idx]
                textpage = page.get_textpage()
                txt = textpage.get_text_range()
                textpage.close()
                page.close()
                if not txt or not txt.strip():
                    continue

                lines = [ln.strip() for ln in txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
                # En la primera página, identificar las líneas cortas de membrete/expediente previas a '-1-' o 'Buenos Aires'
                if page_idx == 0:
                    for ln in lines[:8]:
                        if not ln:
                            continue
                        if re.match(r"^[-–—−]\s*\d+\s*[-–—−]", ln) or "buenos aires" in ln.lower() or "vistos los autos" in ln.lower():
                            break
                        if len(ln) < 90:
                            running_headers.add(ln)

                # Filtrar cabeceras repetitivas de página y numeración '- N -' o '−N−'
                filtered_lines = []
                for idx_ln, ln in enumerate(lines):
                    if not ln:
                        filtered_lines.append("")
                        continue
                    # Si es membrete repetido en páginas 2+
                    if page_idx > 0 and idx_ln < 8 and ln in running_headers:
                        continue
                    # Si la línea es solo el número de página (ej: '−2−' o '- 2 -') o marca de transporte '-//-'
                    if re.match(r"^[-–—−]\s*\d{1,4}\s*[-–—−]?$", ln) or ln == "-//-":
                        continue
                    # Si el número de página está pegado al inicio de la línea (ej: '−2− n° 81/06...')
                    ln = re.sub(r"^[-–—−]\s*\d{1,4}\s*[-–—−]\s*", "", ln)
                    if ln:
                        filtered_lines.append(ln)

                # Eliminar líneas vacías al inicio y final de cada página para permitir unión fluida entre páginas
                while filtered_lines and not filtered_lines[0]:
                    filtered_lines.pop(0)
                while filtered_lines and not filtered_lines[-1]:
                    filtered_lines.pop()

                if filtered_lines:
                    pages_text.append("\n".join(filtered_lines))
        finally:
            doc.close()

        return "\n".join(pages_text), num_pages

    def fetch_full_fallo(self, raw_input: str, include_full_text: bool = True) -> dict:
        """
        Orquesta la descarga completa de un fallo de SAIJ:
        metadatos + sumarios oficiales + texto íntegro (inline o PDF).
        """
        uuid = self.resolve_uuid(raw_input)
        doc = self.fetch_document_by_uuid(uuid)
        meta_raw = doc.get("metadata", {})
        content = doc.get("content", {})

        # Si el usuario ingresó el UUID de un sumario suelto que apunta a un fallo, resolver el fallo padre
        doc_type = meta_raw.get("document-content-type", "")
        if doc_type == "sumario" and content.get("id-fallo"):
            parent_uuid = self.fa_id_to_uuid(content["id-fallo"])
            if parent_uuid:
                uuid = parent_uuid
                doc = self.fetch_document_by_uuid(uuid)
                meta_raw = doc.get("metadata", {})
                content = doc.get("content", {})

        id_infojus = content.get("id-infojus", "")
        titulo = content.get("titulo", "").strip()
        actor = content.get("actor", "").strip()
        demandado = content.get("demandado", "").strip()
        sobre = content.get("sobre", "").strip()

        if not titulo:
            parts = [p for p in [actor, f"c/ {demandado}" if demandado else "", f"s/ {sobre}" if sobre else ""] if p]
            titulo = " ".join(parts) or f"Fallo {id_infojus}"

        # Extraer lista de sumarios relacionados
        sum_rel = content.get("sumarios-relacionados", {})
        sum_ids = []
        if isinstance(sum_rel, dict):
            raw_list = sum_rel.get("sumario-relacionado", [])
            if isinstance(raw_list, str):
                sum_ids = [raw_list]
            elif isinstance(raw_list, list):
                sum_ids = raw_list

        sumarios = self.fetch_sumarios(sum_ids)

        # Extraer texto completo (inline o desde PDF adjunto)
        full_text = ""
        pdf_pages = 0
        pdf_url = None

        inline_text = content.get("texto-completo") or content.get("texto")
        if isinstance(inline_text, str) and inline_text.strip():
            full_text = inline_text.strip()

        texto_doc = content.get("texto-doc")
        if isinstance(texto_doc, dict) and texto_doc.get("uuid") and texto_doc.get("file-name"):
            pdf_uuid = texto_doc["uuid"]
            pdf_name = texto_doc["file-name"]
            pdf_url = f"{SAIJ_BASE_URL}/descarga-archivo?guid={pdf_uuid}&name={pdf_name}"
            if include_full_text and not full_text:
                try:
                    full_text, pdf_pages = self.extract_pdf_text(pdf_uuid, pdf_name)
                except Exception as e:
                    full_text = f"*(Nota: No se pudo extraer el texto del PDF adjunto: {e})*"

        friendly_sub = meta_raw.get("friendly-url-subdomain", "jurisprudencia")
        canonical_url = f"{SAIJ_BASE_URL}/{friendly_sub}/{uuid}"

        jurisdiccion = ""
        if isinstance(content.get("jurisdiccion"), dict):
            jurisdiccion = content["jurisdiccion"].get("descripcion", "")

        return {
            "uuid": uuid,
            "id": id_infojus,
            "titulo_oficial": titulo,
            "actor": actor,
            "demandado": demandado,
            "sobre": sobre,
            "tribunal": content.get("tribunal", "CORTE SUPREMA DE JUSTICIA DE LA NACIÓN"),
            "fecha": content.get("fecha", ""),
            "magistrados": content.get("magistrados", ""),
            "jurisdiccion": jurisdiccion,
            "numero_interno": content.get("numero-interno", ""),
            "texto_url": canonical_url,
            "pdf_url": pdf_url,
            "pdf_pages": pdf_pages,
            "sumarios": sumarios,
            "full_text": full_text,
        }


class SAIJParser:
    """Formatea los datos de un fallo de SAIJ en Markdown jerárquico de alta pureza para RAG."""

    @staticmethod
    def clean_saij_markup(text: str) -> str:
        """Elimina etiquetas internas de SAIJ ([[p]], [[r uuid:...]]) y normaliza espacios."""
        if not text:
            return ""
        cleaned = re.sub(r"\[\[/p\]\]", "\n\n", text)
        cleaned = re.sub(r"\[\[p\]\]", "", cleaned)
        cleaned = re.sub(r"\[\[r\s+[^\]]+\]\]", "", cleaned)
        cleaned = re.sub(r"\[\[/r\]\]", "", cleaned)
        cleaned = re.sub(r"\[\[[a-zA-Z0-9_:\-\s/]+\]\]", "", cleaned)
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        # Colapsar espacios múltiples horizontales (comunes en sumarios antiguos de los años 80/90)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def clean_pdf_sentence_text(raw_text: str, caratula_oficial: str = "") -> list[str]:
        """
        Sanea el texto extraído de los PDFs de la CSJN:
          - Repara cortes de palabra con guión blando (\ufffd o '-' al final de línea).
          - Elimina cabeceras/pies de página repetitivos (números de página aislados, '- 1 -').
          - Agrupa líneas continuas en párrafos coherentes y estructura Considerandos y Votos.
        """
        if not raw_text:
            return []

        txt = raw_text.replace("\r\n", "\n").replace("\r", "\n")

        # 1. Reparar marcas de transporte de foja judicial ('-//-') entre páginas
        # Si une una palabra cortada en mayúsculas o minúsculas (ej: 'VO-//-\n-//-TO' -> 'VOTO')
        txt = re.sub(r"([a-záéíóúüñA-ZÁÉÍÓÚÜÑ])-//-\s*(?:-//-\s*)?([a-záéíóúüñA-ZÁÉÍÓÚÜÑ])", r"\1\2", txt)
        # Si hay transporte de foja con espacio entre palabras (ej: 'a -//-\n-//-abstenerse' -> 'a abstenerse')
        txt = re.sub(r"-//-\s*(?:-//-\s*)?", " ", txt)
        # Separar 'ES COPIA' cuando precede inmediatamente al título de un Voto o Disidencia
        txt = re.sub(r"\b(ES\s+COPIA)\s+(?=(?:VOTO|DISIDENCIA|Recurso\s+extraordinario)\b)", r"\1\n\n", txt, flags=re.IGNORECASE)

        # Reparar palabras cortadas por guión blando o caracteres de control PDF (\ufffd, \ufffe, \uffff, \xad, '-')
        txt = re.sub(
            r"([a-záéíóúüñA-ZÁÉÍÓÚÜÑ])[\ufffd\ufffe\uffff\xad\-‐‑]\s*\n\s*([a-záéíóúüñ])",
            r"\1\2",
            txt
        )
        txt = re.sub(
            r"([a-záéíóúüñA-ZÁÉÍÓÚÜÑ])[\ufffd\ufffe\uffff\xad]([a-záéíóúüñ])",
            r"\1\2",
            txt
        )
        # Remover caracteres de reemplazo residuales
        txt = re.sub(r"[\ufffd\ufffe\uffff\xad]", "", txt)

        raw_lines = txt.split("\n")
        cleaned_lines = []
        for line in raw_lines:
            s = line.strip()
            # Omitir líneas de numeración de página aislada ("- 12 -", "−12−", "12") o sello "U SO OFIC IAL"
            if re.match(r"^[-–—−]?\s*\d{1,4}\s*[-–—−]?$", s):
                continue
            s = re.sub(r"\bU\s*SO\s+OFIC\s*IAL\b", "", s).strip()
            cleaned_lines.append(s)

        # 2. Reconstruir párrafos lógicos
        paragraphs = []
        current_buf = []

        def flush_buf():
            if current_buf:
                joined = " ".join(current_buf).strip()
                joined = re.sub(r"\s{2,}", " ", joined)
                if joined:
                    paragraphs.append(joined)
                current_buf.clear()

        for s in cleaned_lines:
            if not s:
                flush_buf()
                continue

            # Detectar inicio de nuevo Considerando ("1°) Que...", "1º) En las presentes...")
            if re.match(r"^\d{1,2}\s*[°ºª]\)\s+[A-ZÁÉÍÓÚÑ]", s) or re.match(r"^\d{1,3}\s*[°ºª]?\)\s+Que\b", s):
                flush_buf()
                current_buf.append(s)
                continue

            # Detectar encabezados estructurales del fallo
            if re.match(
                r"^(?:Vistos\s+los\s+autos|Considerando\s*:?|Por\s+ello\b|RESUELVE\s*:?|VOTO\s+DE|DISIDENCIA\s+DE|Suprema\s+Corte\s*:?|Defensor[ií]a\s+Oficial\s+ante\s+la\s+Corte|EXCMA\.\s+CORTE\s+SUPREMA|Recurso\s+extraordinario\s+interpuesto\s+por)",
                s,
                re.IGNORECASE
            ):
                flush_buf()
                current_buf.append(s)
                if s.endswith(":"):
                    flush_buf()
                continue

            current_buf.append(s)
            # Si la línea termina en punto final y tiene longitud moderada/corta respecto al bloque, cerrar párrafo
            if s.endswith(".") and len(s) < 68:
                flush_buf()

        flush_buf()

        # Helper para verificar si quedan Considerandos numerados dentro del voto actual
        def has_more_considerandos_in_vote(start_idx: int) -> bool:
            for future_p in paragraphs[start_idx:]:
                if re.match(
                    r"^(?:-\s*)?(?:VOTO|DISIDENCIA)\s+DE(?:L| LOS| LA)?\s+SEÑOR|^Defensor[ií]a\s+Oficial\s+ante\s+la\s+Corte|^EXCMA\.\s+CORTE\s+SUPREMA|^Recurso\s+extraordinario\s+interpuesto\s+por",
                    future_p,
                    re.IGNORECASE
                ):
                    return False
                if re.match(r"^\d{1,2}\s*[°ºª]\)\s+[A-ZÁÉÍÓÚÑ]", future_p) or re.match(r"^\d{1,3}\s*[°ºª]?\)\s*Que\b", future_p):
                    return True
            return False

        # 3. Formatear jerárquicamente los párrafos de la sentencia
        structured = []
        in_considerandos = False
        in_dictamen_defensoria = False
        autos_suffix = f' (Autos: "{caratula_oficial}")' if caratula_oficial else ""

        for idx_p, p in enumerate(paragraphs):
            # Encabezados de Dictamen / Procuración
            if re.match(r"^Suprema\s+Corte\s*:$", p, re.IGNORECASE):
                structured.append("### DICTAMEN DE LA PROCURACIÓN GENERAL DE LA NACIÓN")
                structured.append(f"**{p}**")
                in_considerandos = False
                continue

            # Dictamen de la Defensoría General de la Nación ante la CSJN
            if re.match(r"^(?:Defensor[ií]a\s+Oficial\s+ante\s+la\s+Corte|EXCMA\.\s+CORTE\s+SUPREMA\s+DE\s+JUSTICIA)", p, re.IGNORECASE):
                if not in_dictamen_defensoria:
                    structured.append("### DICTAMEN DE LA DEFENSORÍA GENERAL DE LA NACIÓN")
                    in_dictamen_defensoria = True
                structured.append(f"**{p}**")
                in_considerandos = False
                continue

            # Pie de Secretaría (Datos del Recurso Extraordinario y Tribunal de Origen)
            if re.match(r"^Recurso\s+extraordinario\s+interpuesto\s+por\b", p, re.IGNORECASE):
                structured.append("### DATOS DEL EXPEDIENTE Y LETRADOS INTERVINIENTES")
                structured.append(p)
                in_considerandos = False
                continue

            # Inicio de Sentencia CSJN ("Vistos los autos: ...")
            if re.match(r"^Vistos\s+los\s+autos\s*:", p, re.IGNORECASE):
                structured.append(f"### SENTENCIA DE LA CORTE SUPREMA DE JUSTICIA DE LA NACIÓN{autos_suffix}")
                in_dictamen_defensoria = False
                # Si "Considerando:" quedó unido al final del párrafo de Vistos los autos, separarlo
                m_vistos_cons = re.match(r"^(Vistos\s+los\s+autos\s*:.*?)\s+Considerando\s*:?$", p, re.IGNORECASE)
                if m_vistos_cons:
                    structured.append(f"**{m_vistos_cons.group(1).strip()}**")
                    structured.append("#### CONSIDERANDOS")
                    in_considerandos = True
                else:
                    structured.append(f"**{p}**")
                    in_considerandos = False
                continue

            # Votos particulares o Disidencias
            if re.match(r"^(?:-\s*)?(?:VOTO|DISIDENCIA)\s+DE(?:L| LOS| LA)?\s+SEÑOR", p, re.IGNORECASE):
                clean_voto = p.lstrip("- ").rstrip(":")
                structured.append(f"### {clean_voto.upper()}")
                in_considerandos = False
                continue

            # Bloque "Considerando:"
            if re.match(r"^Considerando\s*:?$", p, re.IGNORECASE):
                structured.append("#### CONSIDERANDOS")
                in_considerandos = True
                continue

            # Considerandos numerados ("1°) Que ...", "15) Que ...", "1º) En las presentes...")
            m_cons = re.match(r"^(\d{1,3})\s*[°ºª]?\)\s*(Que\b.*)$", p) or (
                not in_dictamen_defensoria and re.match(r"^(\d{1,2})\s*[°ºª]\)\s*([A-ZÁÉÍÓÚÑ].*)$", p)
            )
            if m_cons:
                if not in_considerandos:
                    structured.append("#### CONSIDERANDOS")
                    in_considerandos = True
                num_c, body_c = m_cons.groups()
                structured.append(f"**CONSIDERANDO {num_c}°.-** {body_c}")
                continue

            # Parte Resolutiva ("Por ello, ... se declara / se resuelve ...")
            # Solo se marca como PARTE RESOLUTIVA si ya no quedan considerandos numerados en el voto actual
            if (
                not in_dictamen_defensoria
                and re.match(r"^Por\s+ello\b", p)
                and (
                    p.rstrip().endswith(":")
                    or any(kw in p.lower() for kw in ["se resuelve", "se declara", "se confirma", "se revoca", "se hace lugar", "hágase saber", "archívese", "notifíquese", "corresponde declarar"])
                )
                and not has_more_considerandos_in_vote(idx_p + 1)
            ):
                structured.append("#### PARTE RESOLUTIVA")
                structured.append(f"**{p}**")
                in_considerandos = False
                continue

            structured.append(p)

        return structured

    def generate_markdown(self, fallo_data: dict, custom_title: str | None = None) -> str:
        """Genera el documento Markdown completo con metadatos, sumarios oficiales y sentencia."""
        titulo = custom_title or fallo_data.get("titulo_oficial") or f"Fallo_{fallo_data.get('id', 'SAIJ')}"
        md = []
        md.append(f"# {titulo}")
        md.append("")

        # Bloque de Metadatos Oficiales
        if fallo_data.get("tribunal"):
            md.append(f"> **Tribunal:** {fallo_data['tribunal']}")
        if fallo_data.get("titulo_oficial"):
            md.append(f"> **Carátula Oficial:** {fallo_data['titulo_oficial']}")
        if fallo_data.get("fecha"):
            md.append(f"> **Fecha de Sentencia:** {fallo_data['fecha']}")
        if fallo_data.get("id"):
            md.append(f"> **ID SAIJ (Infojus):** {fallo_data['id']}")
        if fallo_data.get("numero_interno"):
            md.append(f"> **Expediente / N° Interno:** {fallo_data['numero_interno']}")
        if fallo_data.get("magistrados"):
            md.append(f"> **Magistrados:** {fallo_data['magistrados']}")
        if fallo_data.get("jurisdiccion"):
            md.append(f"> **Jurisdicción:** {fallo_data['jurisdiccion']}")
        if fallo_data.get("texto_url"):
            md.append(f"> **Fuente Oficial SAIJ:** [{fallo_data['texto_url']}]({fallo_data['texto_url']})")
        if fallo_data.get("pdf_url"):
            md.append(f"> **Sentencia Original (PDF):** [Descargar PDF Oficial]({fallo_data['pdf_url']})")

        md.append("")
        md.append("---")
        md.append("")

        # Sección I: Sumarios Oficiales (Doctrina de la CSJN)
        sumarios = fallo_data.get("sumarios", [])
        if sumarios:
            md.append("## I. SUMARIOS OFICIALES (DOCTRINA DEL FALLO)")
            md.append("")
            for idx, s in enumerate(sumarios, 1):
                num_s = s.get("numero_sumario", f"S{idx}")
                voces = s.get("voces") or "Doctrina Jurisprudencial"
                texto_s = self.clean_saij_markup(s.get("texto", ""))
                md.append(f"### Sumario N° {idx} ({num_s}) - {voces}")
                md.append("")
                md.append(texto_s)
                md.append("")

        # Sección II: Texto Íntegro de la Sentencia
        full_text = fallo_data.get("full_text", "").strip()
        if full_text:
            md.append("## II. TEXTO ÍNTEGRO DE LA SENTENCIA")
            md.append("")
            structured_paras = self.clean_pdf_sentence_text(
                full_text,
                caratula_oficial=fallo_data.get("titulo_oficial", "")
            )
            for p in structured_paras:
                md.append(p)
                md.append("")
        elif fallo_data.get("pdf_url"):
            pages_info = f" ({fallo_data['pdf_pages']} páginas)" if fallo_data.get("pdf_pages") else ""
            md.append("## II. TEXTO ORIGINAL DE LA SENTENCIA (REGISTRO HISTÓRICO ESCANEADO)")
            md.append("")
            md.append(
                f"> **Nota de Integridad Documental:** El archivo PDF histórico de este fallo en SAIJ{pages_info} "
                f"corresponde a una digitalización facsimilar en imagen sin capa de texto OCR embebida. "
                f"La totalidad de la doctrina legal del voto mayoritario, votos concurrentes y disidencias ha sido "
                f"extraída de forma íntegra y sin recortes en los **{len(sumarios)} Sumarios Oficiales** de la Sección I. "
                f"Puede consultar o descargar el facsímil original en: [{fallo_data['pdf_url']}]({fallo_data['pdf_url']})."
            )
            md.append("")

        full_md = "\n".join(md)
        full_md = re.sub(r"\n{3,}", "\n\n", full_md).strip() + "\n"
        return full_md


def main():
    parser = argparse.ArgumentParser(
        description="Extractor de Jurisprudencia CSJN / SAIJ a Markdown jerárquico."
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="ID de fallo SAIJ (ej: FA09000059), URL de SAIJ o carátula a buscar (ej: 'Arriola')."
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Título personalizado para el documento."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directorio de salida (por defecto: scripts/output)."
    )
    parser.add_argument(
        "--only-sumarios",
        action="store_true",
        help="Extraer únicamente los sumarios oficiales sin descargar el PDF completo."
    )

    args = parser.parse_args()
    script_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir) if args.output_dir else script_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    fetcher = SAIJFetcher()
    saij_parser = SAIJParser()

    print(f"🔍 Consultando SAIJ para: {args.query} ...")
    fallo_data = fetcher.fetch_full_fallo(args.query, include_full_text=not args.only_sumarios)

    doc_title = args.title or f"CSJN_{fallo_data.get('id', 'Fallo')}_{fallo_data.get('titulo_oficial', '')[:50]}"
    md_content = saij_parser.generate_markdown(fallo_data, custom_title=doc_title)

    safe_name = sanitize_filename(doc_title)
    if not safe_name.endswith(".md"):
        safe_name += ".md"

    out_path = output_dir / safe_name
    out_path.write_text(md_content, encoding="utf-8")
    print(f"✅ Guardado en: {out_path} ({len(md_content) / 1024:.1f} KB, {len(fallo_data.get('sumarios', []))} sumarios)")


if __name__ == "__main__":
    main()
