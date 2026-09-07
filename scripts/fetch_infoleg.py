#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
InfoLEG Document Scraper & Markdown Converter
=============================================
Descarga y convierte normativas, leyes y decretos de InfoLEG (Argentina) a formato
Markdown limpio y altamente estructurado, optimizado para RAG jerárquico (LanceDB)
y proyectos de procesamiento documental como TECCAM_PDF.

Características:
  - Soporte de URLs directas (.htm), páginas de portal (verNorma.do?id=...) o IDs numéricos.
  - Detección y priorización de texto actualizado (texact.htm) vs texto original (norma.htm).
  - Extracción automática de metadatos oficiales (Boletín Oficial, fecha, tipo, emisor, resumen).
  - Normalización robusta de codificación (windows-1252 / ISO-8859-1 con reemplazo seguro).
  - Limpieza de boilerplate HTML (scripts, estilos, banners, encabezados InfoLEG, mapas, tablas TOC).
  - Detección y formato de jerarquía normativa:
      # Título Documento
      ## LIBRO / PARTE / TÍTULO PRELIMINAR
      ### TÍTULO / VISTO / CONSIDERANDO
      #### CAPÍTULO
      ##### SECCIÓN
      **ARTÍCULO X°.- Epígrafe.** Texto... (compatible con detect_heuristic_header de LanceDB)
      * **a)** Incisos y listas ordenadas
  - Conversión de tablas HTML a tablas Markdown GFM.
  - Ejecución interactiva por consola o parametrizada vía flags CLI (--url, --title).
"""

import os
import sys
import re
import argparse
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

# Auto-bootstrap en el entorno virtual si se ejecuta con python del sistema sin dependencias
try:
    import requests
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    repo_root = Path(__file__).resolve().parent.parent
    for venv_candidate in [repo_root / "venv" / "bin" / "python", repo_root / ".venv" / "bin" / "python"]:
        if venv_candidate.exists() and venv_candidate.resolve() != Path(sys.executable).resolve():
            os.execv(str(venv_candidate), [str(venv_candidate)] + sys.argv)
    print("Error: Se requieren 'requests' y 'beautifulsoup4' ('lxml').", file=sys.stderr)
    print("Instálelas con: pip install requests beautifulsoup4 lxml", file=sys.stderr)
    sys.exit(1)


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

INFOLEG_BASE_URL = "https://servicios.infoleg.gob.ar/infolegInternet/"


class InfoLegFetcher:
    """Descarga y resuelve URLs, metadatos y textos completos desde InfoLEG."""

    def __init__(self, session: requests.Session | None = None, timeout: int = 25):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.timeout = timeout

    def normalize_target_url(self, raw_input: str) -> str:
        """Normaliza la entrada (ID numérico, URL relativa o URL absoluta)."""
        raw = raw_input.strip()
        # Si es solo un número de ID
        if re.match(r"^\d+$", raw):
            return f"{INFOLEG_BASE_URL}verNorma.do?id={raw}"
        # Si no tiene esquema
        if raw.startswith("servicios.infoleg.gob.ar") or raw.startswith("www.infoleg.gob.ar"):
            return f"https://{raw}"
        if not raw.startswith("http://") and not raw.startswith("https://"):
            return f"https://{raw}"
        return raw

    def fetch_page_html(self, url: str) -> tuple[str, str]:
        """
        Descarga una URL y decodifica correctamente windows-1252 / ISO-8859-1.
        Retorna (html_text, final_url).
        """
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()

        # Detección de encoding: InfoLEG usa windows-1252 casi universalmente
        content = resp.content
        encoding = "windows-1252"
        if b"charset=utf-8" in content[:2000].lower():
            encoding = "utf-8"
        elif b"charset=iso-8859-1" in content[:2000].lower() or b"charset=windows-1252" in content[:2000].lower():
            encoding = "windows-1252"

        try:
            html = content.decode(encoding)
        except UnicodeDecodeError:
            html = content.decode("windows-1252", errors="replace")

        return html, resp.url

    def extract_norma_id(self, url: str) -> str | None:
        """Extrae el ID numérico de la norma si está presente en la URL."""
        parsed = urlparse(url)
        # Caso verNorma.do?id=12345
        qs = parse_qs(parsed.query)
        if "id" in qs and qs["id"]:
            return qs["id"][0]
        # Caso anexos/.../12345/norma.htm
        m = re.search(r"/(\d+)/(?:norma|texact)\.htm", parsed.path)
        if m:
            return m.group(1)
        return None

    def fetch_metadata_from_portal(self, norma_id: str) -> dict[str, str]:
        """Obtiene metadatos oficiales del portal verNorma.do."""
        portal_url = f"{INFOLEG_BASE_URL}verNorma.do?id={norma_id}"
        meta = {"id": norma_id, "portal_url": portal_url}
        try:
            html, _ = self.fetch_page_html(portal_url)
            soup = BeautifulSoup(html, "lxml")
            tc = soup.find(id="Textos_Completos") or soup.find(id="resultados")
            if not tc:
                return meta

            # Tipo, número y organismo
            strong = tc.find("strong")
            if strong:
                meta["tipo_numero"] = " ".join(strong.get_text().split())

            # Fecha
            fecha_span = tc.find("span", class_=re.compile(r"azul", re.I))
            if fecha_span:
                meta["fecha"] = fecha_span.get_text().strip()

            # Tema / Rama
            destacado = tc.find("span", class_="destacado")
            if destacado:
                meta["tema"] = destacado.get_text().strip()

            # Título / Sumario
            h1 = tc.find("h1")
            if h1:
                meta["titulo_oficial"] = " ".join(h1.get_text().split())

            # Resumen y Boletín Oficial
            for p in tc.find_all("p"):
                ptxt = p.get_text()
                if "Resumen:" in ptxt:
                    res = ptxt.replace("Resumen:", "").strip()
                    meta["resumen"] = " ".join(res.split())
                elif "Boletín Oficial" in ptxt or "Boletin Oficial" in ptxt:
                    meta["boletin_oficial"] = " ".join(ptxt.split())

            # Enlaces a textos completos
            for a in tc.find_all("a", href=True):
                href = a["href"]
                txt = a.get_text(strip=True).lower()
                full_href = urljoin(portal_url, href)
                if "actualizado" in txt or "texact.htm" in href:
                    meta["url_texto_actualizado"] = full_href
                elif "completo" in txt or "norma.htm" in href:
                    meta["url_texto_completo"] = full_href

        except Exception as e:
            meta["error"] = str(e)

        return meta

    def resolve_full_text(self, target_input: str, prefer_updated: bool = True) -> tuple[str, dict[str, str], str]:
        """
        Resuelve y descarga el texto completo HTML final y los metadatos.
        Retorna (html_content, metadata_dict, final_text_url).
        """
        normalized_url = self.normalize_target_url(target_input)
        norma_id = self.extract_norma_id(normalized_url)

        meta = {}
        if norma_id:
            meta = self.fetch_metadata_from_portal(norma_id)

        # Si el input original ya es un archivo directo .htm
        if normalized_url.endswith(".htm") or normalized_url.endswith(".html"):
            text_url = normalized_url
        else:
            # Seleccionar URL de texto desde metadatos
            if prefer_updated and meta.get("url_texto_actualizado"):
                text_url = meta["url_texto_actualizado"]
            elif meta.get("url_texto_completo"):
                text_url = meta["url_texto_completo"]
            else:
                text_url = normalized_url

        html, final_url = self.fetch_page_html(text_url)
        meta["texto_url"] = final_url
        return html, meta, final_url


class InfoLegParser:
    """Parsea el HTML de InfoLEG y genera Markdown estructurado de alta fidelidad."""

    def __init__(self):
        self.verbs_no_epigraph = {
            "sustitúyese", "deróganse", "derógase", "incorpórase", "apruébase",
            "establécese", "facúltase", "créase", "modifícase", "comuníquese",
            "regístrese", "notifíquese", "déjase", "instrúyese", "desígnase"
        }

    ROMAN_TO_ARABIC = {
        "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
        "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18,
        "XIX": 19, "XX": 20, "XXI": 21, "XXII": 22, "XXIII": 23, "XXIV": 24, "XXV": 25, "XXVI": 26,
        "XXVII": 27, "XXVIII": 28, "XXIX": 29, "XXX": 30
    }
    ARABIC_TO_ROMAN = {v: k for k, v in ROMAN_TO_ARABIC.items()}

    WORD_TO_ROMAN_LIBRO = {
        "PRIMERO": ("LIBRO PRIMERO", "LIBRO I"),
        "SEGUNDO": ("LIBRO SEGUNDO", "LIBRO II"),
        "TERCERO": ("LIBRO TERCERO", "LIBRO III"),
        "CUARTO": ("LIBRO CUARTO", "LIBRO IV"),
        "QUINTO": ("LIBRO QUINTO", "LIBRO V"),
        "SEXTO": ("LIBRO SEXTO", "LIBRO VI"),
        "SEPTIMO": ("LIBRO SÉPTIMO", "LIBRO VII"),
        "SÉPTIMO": ("LIBRO SÉPTIMO", "LIBRO VII"),
        "OCTAVO": ("LIBRO OCTAVO", "LIBRO VIII"),
        "NOVENO": ("LIBRO NOVENO", "LIBRO IX"),
        "DECIMO": ("LIBRO DÉCIMO", "LIBRO X"),
        "DÉCIMO": ("LIBRO DÉCIMO", "LIBRO X"),
    }

    def canonicalize_libro(self, raw_libro: str) -> str:
        """Genera doble denominación canónica para Libros: 'LIBRO SEGUNDO (LIBRO II)'."""
        raw = raw_libro.strip().upper()
        m = re.match(r"^LIBRO\s+(.+)$", raw)
        if not m:
            return raw
        id_part = m.group(1).strip()
        if id_part in self.WORD_TO_ROMAN_LIBRO:
            w_form, r_form = self.WORD_TO_ROMAN_LIBRO[id_part]
            return f"{w_form} ({r_form})"
        if id_part in self.ROMAN_TO_ARABIC:
            arabic = self.ROMAN_TO_ARABIC[id_part]
            word_found = None
            for w, (_, r) in self.WORD_TO_ROMAN_LIBRO.items():
                if r == f"LIBRO {id_part}":
                    word_found = w
                    break
            if word_found:
                return f"LIBRO {word_found} (LIBRO {id_part})"
            return f"LIBRO {id_part} (LIBRO {arabic})"
        dig = re.sub(r"[^\d]", "", id_part)
        if dig.isdigit():
            d_val = int(dig)
            r_val = self.ARABIC_TO_ROMAN.get(d_val)
            if r_val:
                return f"LIBRO {r_val} (LIBRO {d_val})"
        return raw

    def canonicalize_titulo(self, raw_titulo: str) -> str:
        """Genera doble denominación canónica para Títulos: 'TITULO I (TÍTULO 1)'."""
        raw = raw_titulo.strip().upper()
        m = re.match(r"^T[IÍ]TULO\s+(.+)$", raw)
        if not m:
            return raw
        id_part = m.group(1).strip().rstrip("°º.")
        if id_part in self.ROMAN_TO_ARABIC:
            arabic = self.ROMAN_TO_ARABIC[id_part]
            return f"TITULO {id_part} (TÍTULO {arabic})"
        if id_part.isdigit():
            d_val = int(id_part)
            r_val = self.ARABIC_TO_ROMAN.get(d_val)
            if r_val:
                return f"TITULO {r_val} (TÍTULO {d_val})"
        return raw

    def canonicalize_capitulo(self, raw_cap: str) -> str:
        """Genera doble denominación canónica para Capítulos: 'CAPÍTULO I (CAPÍTULO 1)'."""
        raw = raw_cap.strip().upper()
        m = re.match(r"^CAP[IÍ]TULO\s+(.+)$", raw)
        if not m:
            return raw
        id_part = m.group(1).strip().rstrip("°ºª.")
        if id_part in self.ROMAN_TO_ARABIC:
            arabic = self.ROMAN_TO_ARABIC[id_part]
            return f"CAPÍTULO {id_part} (CAPÍTULO {arabic})"
        if id_part.isdigit():
            d_val = int(id_part)
            r_val = self.ARABIC_TO_ROMAN.get(d_val)
            if r_val:
                return f"CAPÍTULO {r_val} (CAPÍTULO {d_val})"
        return raw

    def canonicalize_seccion(self, raw_sec: str) -> str:
        """Genera doble denominación canónica para Secciones: 'SECCIÓN I (SECCIÓN 1)'."""
        raw = raw_sec.strip().upper()
        m = re.match(r"^SECCI[OÓ]N\s+(.+)$", raw)
        if not m:
            return raw
        id_part = m.group(1).strip().rstrip("°ºªa.")
        if id_part in self.ROMAN_TO_ARABIC:
            arabic = self.ROMAN_TO_ARABIC[id_part]
            return f"SECCIÓN {id_part} (SECCIÓN {arabic})"
        if id_part.isdigit():
            d_val = int(id_part)
            r_val = self.ARABIC_TO_ROMAN.get(d_val)
            if r_val:
                return f"SECCIÓN {r_val} (SECCIÓN {d_val})"
        return raw

    def resolve_header_subtitle(
        self,
        paragraphs: list[str],
        current_idx: int,
        stop_pattern: str,
        max_lookahead: int = 4,
        max_len: int = 250
    ) -> tuple[str, list[str], int]:
        """
        Explora los párrafos subsiguientes para capturar el nombre/subtítulo temático
        de una división estructural (Libro, Título, Capítulo, Sección), saltando y
        preservando notas editoriales intermedias ('Nota Infoleg:', etc.).

        Retorna:
            (subtitle, pending_notes, consumed_paragraphs_count)
        """
        total = len(paragraphs)
        pending_notes = []
        consumed = 0
        subtitle = ""

        k = current_idx + 1
        steps = 0

        while k < total and steps < max_lookahead:
            cand = paragraphs[k].strip()
            if not cand:
                k += 1
                consumed += 1
                continue

            # 1. Detectar notas editoriales de InfoLEG o notas de redacción intermedias
            if re.match(r"^\(?\s*Nota\s+(?:Infoleg|de\s+Redacci[oó]n|al\s+texto|aclaratoria)?\s*:", cand, re.IGNORECASE):
                pending_notes.append(cand)
                k += 1
                consumed += 1
                steps += 1
                continue

            # 2. Si choca con otra división estructural o con el articulado, detenerse
            if re.match(stop_pattern, cand, re.IGNORECASE):
                break

            # 3. Si es una tabla Markdown, detenerse
            if cand.startswith("|"):
                break

            # 4. Candidato a subtítulo temático (hasta max_len caracteres)
            # Descartar párrafos narrativos largos o que comiencen con fórmulas dispositivas
            if len(cand) <= max_len and not re.match(r"^(?:VISTO|CONSIDERANDO|DECRETA|RESUELVE|DISPONE)\b", cand, re.IGNORECASE):
                subtitle = cand.strip(" -–—.")
                k += 1
                consumed += 1
                break
            else:
                break

        return subtitle, pending_notes, consumed

    def clean_soup(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Elimina elementos decorativos, scripts, estilos y encabezados web de InfoLEG."""
        # Eliminar tags técnicos
        for s in soup(["script", "style", "noscript", "head", "meta", "iframe", "map", "header"]):
            s.decompose()

        # Eliminar contenedores de navegación de InfoLEG
        for el in soup.find_all(id=["branding", "encabezado_norma", "cleaner", "footer", "menu", "buscador"]):
            el.decompose()

        # Eliminar enlaces de navegación interna de InfoLEG ("Ver Antecedentes Normativos", "Esta norma modifica...")
        for a in soup.find_all("a"):
            txt = a.get_text().strip().lower()
            if "antecedentes normativos" in txt or "esta norma modifica" in txt or "esta norma es complementada" in txt:
                parent = a.parent
                if parent and parent.name in ["div", "p", "b"]:
                    parent.decompose()
                else:
                    a.decompose()

        # Eliminar tablas de índice temático / sumario normativo inicial si existen
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue
            toc_rows = sum(1 for r in rows if re.search(r"\barts?\.?\s*\d+", r.get_text(), re.IGNORECASE))
            if toc_rows >= 2 and (toc_rows / len(rows) >= 0.35 or len(rows) >= 10):
                table_text = table.get_text()[:400].lower()
                if any(kw in table_text for kw in ["libro", "título", "titulo", "capítulo", "capitulo"]):
                    table.decompose()

        return soup

    def convert_tables(self, soup: BeautifulSoup) -> None:
        """Convierte etiquetas <table> a tablas Markdown GFM antes del parseo de texto."""
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = []
                for td in tr.find_all(["td", "th"]):
                    cell_text = td.get_text().strip()
                    cell_clean = re.sub(r"\s+", " ", cell_text).replace("|", "\\|")
                    cells.append(cell_clean)
                if cells and any(c for c in cells):
                    rows.append(cells)

            if not rows:
                table.decompose()
                continue

            max_cols = max(len(r) for r in rows)
            # Normalizar columnas
            normalized_rows = [r + [""] * (max_cols - len(r)) for r in rows]

            # Verificar si es una tabla muy corta de 1 columna (a veces usada como marco de título)
            if max_cols == 1 and len(normalized_rows) <= 2:
                plain_txt = "\n\n" + normalized_rows[0][0] + "\n\n"
                table.replace_with(plain_txt)
                continue

            md_lines = []
            header = normalized_rows[0]
            md_lines.append("| " + " | ".join(header) + " |")
            md_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
            for r in normalized_rows[1:]:
                md_lines.append("| " + " | ".join(r) + " |")

            table_md = "\n\n" + "\n".join(md_lines) + "\n\n"
            table.replace_with(table_md)

    def extract_paragraphs(self, soup: BeautifulSoup) -> list[str]:
        """Extrae párrafos continuos respetando saltos de línea y bloques HTML."""
        # Convertir <br> en saltos de línea
        for br in soup.find_all("br"):
            br.replace_with("\n")

        # Asegurar separación de bloques HTML (evita que <p> o <div> adyacentes se unan)
        block_tags = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "blockquote", "hr"}
        for tag in soup.find_all(block_tags):
            tag.insert_after(NavigableString("\n\n"))

        raw_text = soup.get_text()
        raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        # Reemplazar entidades numéricas frecuentes si sobrevivieron
        raw_text = raw_text.replace("&#8212;", "—").replace("&#8211;", "–").replace("&nbsp;", " ")

        paragraphs = []
        for raw_block in raw_text.split("\n\n"):
            stripped_block = raw_block.strip()
            if not stripped_block:
                continue

            # Preservar líneas de tabla Markdown
            if stripped_block.startswith("|") and stripped_block.endswith("|"):
                for line in stripped_block.splitlines():
                    if line.strip():
                        paragraphs.append(line.strip())
                continue

            # Unir líneas rotas dentro del mismo bloque en un solo párrafo fluido
            normalized_p = " ".join(stripped_block.split())
            if normalized_p:
                paragraphs.append(normalized_p)

        return paragraphs

    def format_article(self, text: str) -> str:
        """
        Formatea un artículo normativo con epígrafe en negrita.
        Ejemplos:
          'ARTICULO 1°.- Fuentes y aplicación. Los casos...' -> '**ARTÍCULO 1°.- Fuentes y aplicación.** Los casos...'
          'ARTICULO 1º — Objeto. La presente ley...' -> '**ARTÍCULO 1°.- Objeto.** La presente ley...'
          'ARTICULO 1° — Apruébase el Código...' -> '**ARTÍCULO 1°.-** Apruébase el Código...'
        """
        m = re.match(
            r"^(ART[IÍ]CULO|Art\.)\s*(\d+[°º]?(?:\s*(?:bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies))?)\s*[\.\-—–:\s]*\s*(.*)$",
            text,
            re.IGNORECASE
        )
        if not m:
            return text

        _, num_raw, rest = m.groups()
        num = num_raw.strip().rstrip(".").replace("º", "°")
        # Asegurar ordinal ° si es solo dígito
        if re.match(r"^\d+$", num):
            num = f"{num}°"

        # Limpiar guiones o puntuaciones residuales al inicio del cuerpo
        rest = re.sub(r"^[\s\.\-—–:]+", "", rest).strip()

        if not rest:
            return f"**ARTÍCULO {num}.-**"

        # Buscar epígrafe inicial: oración corta con punto al final
        epigraph_match = re.match(r"^([A-ZÁÉÍÓÚ][^.\n]{1,65}\.)\s+(.+)$", rest)
        if epigraph_match:
            epigraph, body = epigraph_match.groups()
            first_word = epigraph.split()[0].lower().rstrip(".,-:")
            # Si el epígrafe empieza con un verbo dispositivo común (ej: Sustitúyese), no es un título
            if first_word in self.verbs_no_epigraph:
                return f"**ARTÍCULO {num}.-** {rest}"
            return f"**ARTÍCULO {num}.- {epigraph}** {body}"

        return f"**ARTÍCULO {num}.-** {rest}"

    def format_inciso(self, text: str) -> str:
        """Formatea incisos alfabéticos o numéricos como ítems de lista Markdown."""
        # Incisos alfabéticos: a) texto, b) texto
        m_alpha = re.match(r"^([a-zñ])\)\s+(.+)$", text, re.IGNORECASE)
        if m_alpha:
            letra, body = m_alpha.groups()
            return f"* **{letra.lower()})** {body}"

        # Incisos numéricos: 1) texto, 2) texto
        m_num = re.match(r"^(\d+)\)\s+(.+)$", text)
        if m_num:
            num, body = m_num.groups()
            return f"* **{num})** {body}"

        # Guiones de viñeta: - texto
        if text.startswith("- ") or text.startswith("— "):
            return f"* {text[2:].strip()}"

        return text

    def structure_markdown(self, paragraphs: list[str]) -> list[str]:
        """
        Aplica reglas de jerarquía estructural legal (Libros, Títulos, Capítulos, Secciones)
        combinando títulos multilínea si corresponde.
        """
        structured = []
        i = 0
        total = len(paragraphs)

        while i < total:
            p = paragraphs[i].strip()
            if not p:
                i += 1
                continue

            # Omitir Bloque de Índice Temático Inicial si existe
            norm_p = "".join(c for c in unicodedata.normalize("NFD", p.lower()) if unicodedata.category(c) != "Mn")
            if norm_p in ["indice tematico", "indice general", "sumario", "indice"]:
                i += 1
                while i < total:
                    next_check = paragraphs[i].strip()
                    if re.match(r"^(?:LEY\s+N?°?\s*\d+|DECRETO\s+N?°?\s*\d+|EL SENADO Y CÁMARA|EL SENADO Y CAMARA|SANCIONADA:|ART[IÍ]CULO\s+1[°º]?\b)", next_check, re.IGNORECASE):
                        break
                    if re.match(r"^CODIGO\s+(?:PENAL|CIVIL)", next_check, re.IGNORECASE) and i + 1 < total and re.match(r"^(?:LIBRO|T[IÍ]TULO|ART[IÍ]CULO)", paragraphs[i+1], re.IGNORECASE):
                        break
                    i += 1
                continue

            # Preservar líneas de tabla Markdown
            if p.startswith("|") and p.endswith("|"):
                structured.append(p)
                i += 1
                continue

            # Nivel 1: Macro-estructuras (Libro, Parte, Título Preliminar, Anexos)
            if re.match(r"^ANEXO\s+[IVXLCDM\d]+$", p, re.IGNORECASE):
                structured.append(f"# {p.upper()}")
                i += 1
                continue

            if re.match(r"^T[IÍ]TULO\s+PRELIMINAR$", p, re.IGNORECASE):
                structured.append("## TÍTULO PRELIMINAR")
                i += 1
                continue

            m_libro = re.match(
                r"^(LIBRO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|[IVXLCDM]+|\d+[°º]?))\s*[-–—]?\s*(.*)$",
                p,
                re.IGNORECASE
            )
            if m_libro:
                libro_num, rest = m_libro.groups()
                pending_notes = []
                if not rest:
                    stop_pat = r"^(?:LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|ART[IÍ]CULO|Art\.)\b"
                    rest, pending_notes, consumed = self.resolve_header_subtitle(paragraphs, i, stop_pat)
                    i += consumed

                canon_libro = self.canonicalize_libro(libro_num)
                header_text = f"{canon_libro} - {rest.strip(' -–—.')}" if rest else canon_libro
                structured.append(f"## {header_text}")
                for note in pending_notes:
                    structured.append(note)
                i += 1
                continue

            # Nivel 2: Títulos
            m_tit = re.match(r"^(T[IÍ]TULO\s+(?:[IVXLCDM]+|\d+[°º]?))\s*[-–—]?\s*(.*)$", p, re.IGNORECASE)
            if m_tit:
                tit_num, rest = m_tit.groups()
                pending_notes = []
                if not rest:
                    stop_pat = r"^(?:LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|ART[IÍ]CULO|Art\.)\b"
                    rest, pending_notes, consumed = self.resolve_header_subtitle(paragraphs, i, stop_pat)
                    i += consumed

                canon_tit = self.canonicalize_titulo(tit_num)
                header_text = f"{canon_tit} - {rest.strip(' -–—.')}" if rest else canon_tit
                structured.append(f"### {header_text}")
                for note in pending_notes:
                    structured.append(note)
                i += 1
                continue

            # Nivel 3: Capítulos
            m_cap = re.match(r"^(CAP[IÍ]TULO\s+(?:[IVXLCDM]+|\d+[°ºª]?))\s*[-–—]?\s*(.*)$", p, re.IGNORECASE)
            if m_cap:
                cap_num, rest = m_cap.groups()
                pending_notes = []
                if not rest:
                    stop_pat = r"^(?:LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|ART[IÍ]CULO|Art\.)\b"
                    rest, pending_notes, consumed = self.resolve_header_subtitle(paragraphs, i, stop_pat)
                    i += consumed

                canon_cap = self.canonicalize_capitulo(cap_num)
                header_text = f"{canon_cap} - {rest.strip(' -–—.')}" if rest else canon_cap
                structured.append(f"#### {header_text}")
                for note in pending_notes:
                    structured.append(note)
                i += 1
                continue

            # Nivel 4: Secciones
            m_sec = re.match(r"^(SECCI[OÓ]N\s+(?:\d+[ªºa]?|[IVXLCDM]+))\s*[-–—]?\s*(.*)$", p, re.IGNORECASE)
            if m_sec:
                sec_num, rest = m_sec.groups()
                pending_notes = []
                if not rest:
                    stop_pat = r"^(?:LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|ART[IÍ]CULO|Art\.)\b"
                    rest, pending_notes, consumed = self.resolve_header_subtitle(paragraphs, i, stop_pat)
                    i += consumed

                canon_sec = self.canonicalize_seccion(sec_num)
                header_text = f"{canon_sec} - {rest.strip(' -–—.')}" if rest else canon_sec
                structured.append(f"##### {header_text}")
                for note in pending_notes:
                    structured.append(note)
                i += 1
                continue

            # Bloques formales de Decretos / Leyes
            if p.upper() in ["VISTO:", "VISTO", "CONSIDERANDO:", "CONSIDERANDO"]:
                structured.append(f"### {p.upper().rstrip(':')}")
                i += 1
                continue

            if p.upper() in ["DECRETA:", "RESUELVE:", "DISPONE:"]:
                structured.append(f"### {p.upper()}")
                i += 1
                continue

            # Artículos Normativos
            if re.match(r"^(?:ART[IÍ]CULO|Art\.)\s*\d+", p, re.IGNORECASE):
                structured.append(self.format_article(p))
                i += 1
                continue

            # Incisos / Viñetas
            inciso = self.format_inciso(p)
            structured.append(inciso)
            i += 1

        return structured

    def generate_markdown(self, html: str, meta: dict[str, str], custom_title: str | None = None) -> str:
        """Transforma el HTML completo en documento Markdown con metadatos."""
        soup = BeautifulSoup(html, "lxml")
        self.clean_soup(soup)
        self.convert_tables(soup)
        paragraphs = self.extract_paragraphs(soup)
        structured_lines = self.structure_markdown(paragraphs)

        # Construir cabecera del documento Markdown
        doc_title = custom_title or meta.get("titulo_oficial") or meta.get("norma") or "Documento Normativo InfoLEG"
        md_output = []
        md_output.append(f"# {doc_title}")
        md_output.append("")

        # Bloque de metadatos oficiales
        meta_quotes = []
        if meta.get("tipo_numero"):
            meta_quotes.append(f"> **Norma:** {meta['tipo_numero']}")
        if meta.get("tema"):
            meta_quotes.append(f"> **Rama / Categoría:** {meta['tema']}")
        if meta.get("fecha"):
            meta_quotes.append(f"> **Fecha:** {meta['fecha']}")
        if meta.get("boletin_oficial"):
            meta_quotes.append(f"> **Publicación:** {meta['boletin_oficial']}")
        if meta.get("texto_url"):
            meta_quotes.append(f"> **Fuente Oficial:** [{meta['texto_url']}]({meta['texto_url']})")
        if meta.get("resumen"):
            meta_quotes.append(f">\n> **Resumen Oficial:**\n> {meta['resumen']}")

        if meta_quotes:
            md_output.extend(meta_quotes)
            md_output.append("")
            md_output.append("---")
            md_output.append("")

        # Agregar cuerpo estructurado asegurando espaciado limpio
        prev_is_header = False
        prev_is_list = False
        for line in structured_lines:
            is_header = line.startswith("#")
            is_list = line.startswith("* ")
            if is_header and not prev_is_header:
                md_output.append("")
            if not is_list and prev_is_list:
                md_output.append("")
            md_output.append(line)
            if not is_list:
                md_output.append("")
            prev_is_header = is_header
            prev_is_list = is_list

        # Compactar saltos de línea repetidos
        full_md = "\n".join(md_output)
        full_md = re.sub(r"\n{3,}", "\n\n", full_md).strip() + "\n"
        return full_md


def sanitize_filename(name: str) -> str:
    """Convierte un título en un nombre de archivo seguro y portable."""
    # Reemplazar caracteres no permitidos en sistemas de archivos
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    # Reemplazar espacios y guiones múltiples por guiones bajos
    clean = re.sub(r"\s+", "_", clean).strip("_")
    # Remover tildes y caracteres especiales para máxima portabilidad
    replacements = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"),
        ("ñ", "n"), ("Ñ", "N"), ("º", ""), ("°", "")
    )
    for orig, rep in replacements:
        clean = clean.replace(orig, rep)
    # Limitar longitud si fuera necesario
    return clean[:120] or "documento_infoleg"


def main():
    parser = argparse.ArgumentParser(
        description="Extractor y conversor de normativas de InfoLEG a Markdown jerárquico."
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="URL de InfoLEG o ID numérico de la norma (ej: 409377 o URL de verNorma / anexo)."
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Título o nombre descriptivo para el archivo (ej: Ley_26639_Glaciares)."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directorio de destino (por defecto: scripts/output relativo a este repositorio)."
    )
    parser.add_argument(
        "--prefer-original",
        action="store_true",
        help="Priorizar texto original (norma.htm) sobre texto actualizado (texact.htm)."
    )

    args = parser.parse_args()

    # Directorio de salida dinámico y portable (Ley Universal de Portabilidad)
    script_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir) if args.output_dir else script_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Solicitar URL interactivamente si no se pasó por flag
    raw_url = args.url
    if not raw_url:
        print("\n=======================================================")
        print("🏛️  Extractor de Normativa InfoLEG a Markdown Jerárquico")
        print("=======================================================")
        try:
            raw_url = input("🌐 Ingrese la URL o ID numérico de InfoLEG: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperación cancelada por el usuario.")
            sys.exit(0)

    if not raw_url:
        print("❌ Error: Debe especificar una URL o un ID de InfoLEG válido.", file=sys.stderr)
        sys.exit(1)

    fetcher = InfoLegFetcher()
    doc_parser = InfoLegParser()

    print(f"\n[1/3] Resolviendo documento en InfoLEG ({raw_url})...")
    prefer_updated = not args.prefer_original
    try:
        html, meta, text_url = fetcher.resolve_full_text(raw_url, prefer_updated=prefer_updated)
        print(f"      ✓ Fuente resuelta: {text_url}")
        if meta.get("tipo_numero"):
            print(f"      ✓ Norma: {meta['tipo_numero']}")
        if meta.get("fecha"):
            print(f"      ✓ Fecha: {meta['fecha']}")
    except Exception as e:
        print(f"❌ Error al descargar de InfoLEG: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Solicitar título si no se pasó por flag
    doc_title = args.title
    if not doc_title:
        default_suggestion = meta.get("titulo_oficial") or meta.get("tipo_numero") or "Documento_InfoLEG"
        default_safe = sanitize_filename(default_suggestion)
        try:
            prompt_str = f"📄 Ingrese el título para el archivo Markdown [{default_safe}]: "
            entered = input(prompt_str).strip()
            doc_title = entered if entered else default_safe
        except (KeyboardInterrupt, EOFError):
            doc_title = default_safe

    # 3. Parsear y estructurar en Markdown
    print("\n[2/3] Procesando DOM, depurando navegación y jerarquizando articulado...")
    markdown_content = doc_parser.generate_markdown(html, meta, custom_title=doc_title)

    # 4. Guardar archivo
    safe_filename = sanitize_filename(doc_title)
    if not safe_filename.endswith(".md"):
        safe_filename += ".md"
    output_path = output_dir / safe_filename

    print(f"\n[3/3] Guardando Markdown en: {output_path.name}...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # Estadísticas finales
    size_kb = output_path.stat().st_size / 1024
    lines_count = len(markdown_content.splitlines())
    art_count = len(re.findall(r"\*\*ART[IÍ]CULO\s+\d+", markdown_content, re.IGNORECASE))

    print("\n=======================================================")
    print("✅ ¡Documento extraído y estructurado exitosamente!")
    print(f"   📁 Archivo: {output_path}")
    print(f"   📊 Tamaño: {size_kb:.1f} KB | {lines_count} líneas")
    print(f"   ⚖️  Artículos detectados y formateados: {art_count}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
