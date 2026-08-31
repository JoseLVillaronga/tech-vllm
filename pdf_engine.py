#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Generación de Documentos y Contratos en PDF para vLLM Suite Gateway.
Genera documentos PDF estándar A4 sin dependencias externas pesadas, con soporte
de caracteres en español, fórmulas químicas/matemáticas limpias, eliminación de emojis,
paginación exacta, centrado simétrico y descarga directa vía HTTP.
"""

import io
import os
import zlib
import re
import uuid
from typing import Optional, Dict, Any, List

PDF_STORAGE_DIR = "/home/jose/vllm/outputs/pdfs"
os.makedirs(PDF_STORAGE_DIR, exist_ok=True)

# Métricas aproximadas de ancho de caracteres para fuentes estándar Helvetica / Helvetica-Bold
HELVETICA_WIDTHS = {
    ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667, '\'': 191,
    '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
    ':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556, '@': 1015,
    '[': 278, '\\': 278, ']': 278, '^': 469, '_': 556, '{': 334, '|': 260, '}': 334, '~': 584
}

HELVETICA_BOLD_WIDTHS = {
    ' ': 278, '!': 333, '"': 474, '#': 556, '$': 556, '%': 889, '&': 722, '\'': 238,
    '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
    ':': 333, ';': 333, '<': 584, '=': 584, '>': 584, '?': 611, '@': 975,
    '[': 333, '\\': 278, ']': 333, '^': 584, '_': 556, '{': 389, '|': 280, '}': 389, '~': 584
}


def clean_latex(text: str) -> str:
    r"""Convierte fórmulas matemáticas y químicas LaTeX (ej: $\text{CO}_2$, $1.5^{\circ}\text{C}$) a texto legible."""
    latex_symbols = {
        r'^{\circ}': '°',
        r'^\circ': '°',
        r'\circ': '°',
        r'\degree': '°',
        r'\pm': '±',
        r'\cdot': '*',
        r'\times': 'x',
        r'\div': '/',
        r'\approx': '≈',
        r'\le': '<=',
        r'\ge': '>=',
        r'\neq': '!=',
    }
    for k, v in latex_symbols.items():
        text = text.replace(k, v)

    # Eliminar envoltorios \text{...}
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    # Limpiar subíndices (ej: CO_2 o N_{2}O -> CO2, N2O)
    text = re.sub(r'([A-Za-z0-9°]+)_\{?([0-9A-Za-z]+)\}?', r'\1\2', text)
    # Limpiar superíndices (ej: CO^2 o m^3 -> CO^2, m^3)
    text = re.sub(r'([A-Za-z0-9°]+)\^\{?([0-9A-Za-z]+)\}?', r'\1^\2', text)
    # Remover símbolos delimitadores $
    text = text.replace('$', '')
    return text


def clean_emojis(text: str) -> str:
    """Remueve emojis y caracteres especiales fuera del mapa WinAnsi/Latin-1 para evitar signos '?' en el PDF."""
    emoji_pattern = re.compile(
        '['
        '\U00010000-\U0010ffff'  # Emojis suplementarios
        '\u2600-\u27bf'          # Símbolos misceláneos
        '\u2300-\u23ff'          # Símbolos técnicos
        '\u2b50\u2b55\u2934\u2935\u200d\ufe0f\ufe0e'
        ']+', flags=re.UNICODE
    )
    return emoji_pattern.sub('', text)


def sanitize_text_for_pdf(text: str) -> str:
    """Limpia fórmulas LaTeX, emojis y reemplaza caracteres tipográficos para compatibilidad con WinAnsi/Latin-1."""
    text = clean_latex(text)
    text = clean_emojis(text)
    replacements = {
        "—": " - ",
        "–": "-",
        "“": "\"",
        "”": "\"",
        "‘": "\x27",
        "’": "\x27",
        "…": "...",
        "•": "*",
        "·": "*",
        "™": "(TM)",
        "©": "(C)",
        "®": "(R)",
        "\u200b": "",
        "\ufeff": "",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    # Filtrar caracteres no encodables en latin-1 para evitar signos '?' arbitrarios
    clean_chars = []
    for ch in text:
        try:
            ch.encode("latin-1")
            clean_chars.append(ch)
        except UnicodeEncodeError:
            pass
    return "".join(clean_chars)


def get_text_width(text: str, font: str = "F1", size: float = 10.5) -> float:
    """Calcula el ancho exacto en puntos tipográficos de un string."""
    is_bold = font in ("F2", "F4")
    w_table = HELVETICA_BOLD_WIDTHS if is_bold else HELVETICA_WIDTHS
    total_units = 0
    for ch in text:
        if ch.isupper():
            w = w_table.get(ch, 722 if is_bold else 667)
        elif ch.islower():
            w = w_table.get(ch, 556 if is_bold else 500)
        elif ch.isdigit():
            w = 556
        else:
            w = w_table.get(ch, 350)
        total_units += w
    return (total_units / 1000.0) * size


class PDFDocumentBuilder:
    """Compilador de documentos PDF A4 en memoria con soporte de Markdown y paginación precisa."""

    def __init__(self, page_size=(595.28, 841.89), company_name: str = "Documento Oficial"):
        self.width, self.height = page_size
        self.margin_x = 54.0  # ~1.9 cm
        self.margin_y = 54.0
        self.printable_width = self.width - 2 * self.margin_x
        self.pages = []
        self.current_page_stream = []
        self.y = self.height - self.margin_y
        self.footer_text = sanitize_text_for_pdf(company_name)

    def new_page(self):
        if self.current_page_stream:
            self.pages.append(self.current_page_stream)
            self.current_page_stream = []
        self.y = self.height - self.margin_y

    def check_page_break(self, needed_height: float):
        if self.y - needed_height < self.margin_y + 35:
            self.new_page()

    def wrap_text_precise(self, text: str, font: str = "F1", size: float = 10.5, max_width: Optional[float] = None) -> List[str]:
        """Ajusta el texto a líneas múltiples calculando el ancho real de cada palabra."""
        if max_width is None:
            max_width = self.printable_width

        words = text.split(" ")
        lines = []
        current_line = []
        current_w = 0.0
        space_w = get_text_width(" ", font, size)

        for word in words:
            if not word:
                continue
            word_w = get_text_width(word, font, size)
            needed = word_w if not current_line else (current_w + space_w + word_w)
            if needed <= max_width:
                current_line.append(word)
                current_w = needed
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_w = word_w

        if current_line:
            lines.append(" ".join(current_line))
        return lines if lines else [""]

    def add_wrapped_paragraph(self, text: str, font: str = "F1", size: float = 10.5, line_height: float = 14.0, align: str = "left", indent: float = 0.0):
        clean = sanitize_text_for_pdf(text)
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)
        clean = re.sub(r"\*(.*?)\*", r"\1", clean)
        clean = re.sub(r"`(.*?)`", r"\1", clean)
        clean = clean.strip()
        if not clean:
            return

        avail_width = self.printable_width - indent
        lines = self.wrap_text_precise(clean, font, size, max_width=avail_width)

        for i, line in enumerate(lines):
            self.check_page_break(line_height)
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            line_w = get_text_width(line, font, size)

            if align == "center":
                x = self.margin_x + max(0.0, (self.printable_width - line_w) / 2.0)
            elif align == "right":
                x = self.margin_x + max(0.0, self.printable_width - line_w)
            else:
                x = self.margin_x + (indent if i == 0 else 0)

            self.current_page_stream.append(f"BT /{font} {size} Tf {x:.2f} {self.y:.2f} Td ({safe_line}) Tj ET")
            self.y -= line_height

    def add_separator_line(self):
        self.check_page_break(15)
        self.y -= 4
        self.current_page_stream.append(f"0.5 w 0.7 0.7 0.7 RG {self.margin_x:.2f} {self.y:.2f} m {self.width - self.margin_x:.2f} {self.y:.2f} l S")
        self.y -= 10

    def add_signatures(self, name_left="FIRMA DE LA PARTE LOCADORA / CLIENTE", name_right="FIRMA DE LA PARTE LOCATARIA / PRESTADOR"):
        self.check_page_break(85)
        self.y -= 40
        w_box = (self.printable_width - 40) / 2

        x_left_start = self.margin_x
        x_left_end = self.margin_x + w_box

        x_right_start = self.width - self.margin_x - w_box
        x_right_end = self.width - self.margin_x

        self.current_page_stream.append(f"0.7 w 0 0 0 RG {x_left_start:.2f} {self.y:.2f} m {x_left_end:.2f} {self.y:.2f} l S")
        self.current_page_stream.append(f"0.7 w 0 0 0 RG {x_right_start:.2f} {self.y:.2f} m {x_right_end:.2f} {self.y:.2f} l S")

        self.y -= 14
        lbl_l = sanitize_text_for_pdf(name_left).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lbl_r = sanitize_text_for_pdf(name_right).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        self.current_page_stream.append(f"BT /F1 8.5 Tf {x_left_start:.2f} {self.y:.2f} Td ({lbl_l}) Tj ET")
        self.current_page_stream.append(f"BT /F1 8.5 Tf {x_right_start:.2f} {self.y:.2f} Td ({lbl_r}) Tj ET")
        self.y -= 15

    def add_table(self, table_lines: List[str]):
        """Renderiza una tabla Markdown con diseño profesional, bordes y cabecera destacada."""
        if not table_lines:
            return

        parsed_rows = []
        for line in table_lines:
            # Saltar la línea separadora (ej: | :--- | :--- |)
            if re.match(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$", line):
                continue
            parts = [p.strip() for p in line.split("|")]
            if parts and parts[0] == "":
                parts.pop(0)
            if parts and parts[-1] == "":
                parts.pop()
            if parts:
                parsed_rows.append(parts)

        if not parsed_rows:
            return

        header_row = parsed_rows[0]
        num_cols = len(header_row)
        if num_cols == 0:
            return

        # Normalizar número de columnas en todas las filas
        normalized_rows = []
        for r in parsed_rows:
            row_cells = r[:num_cols]
            while len(row_cells) < num_cols:
                row_cells.append("")
            normalized_rows.append(row_cells)

        header_cells = normalized_rows[0]
        content_rows = normalized_rows[1:]

        # 1. Calcular anchos proporcionales de columnas
        col_max_lens = [max(1, len(header_cells[c])) for c in range(num_cols)]
        for r in content_rows:
            for c in range(num_cols):
                col_max_lens[c] = max(col_max_lens[c], len(r[c]))

        sum_lens = sum(col_max_lens)
        avail_w = self.printable_width
        col_widths = []

        for c in range(num_cols):
            prop_w = (col_max_lens[c] / sum_lens) * avail_w
            min_w = max(40.0, avail_w / (num_cols * 2))
            col_widths.append(max(min_w, prop_w))

        total_calc_w = sum(col_widths)
        scale_factor = avail_w / total_calc_w
        col_widths = [w * scale_factor for w in col_widths]

        font_header = "F2"
        size_header = 9.0
        font_body = "F1"
        size_body = 8.5
        cell_padding_h = 5.0
        cell_padding_v = 4.0
        line_height_body = 11.5

        def render_single_row(row_items: List[str], is_header: bool = False, is_even: bool = False):
            wrapped_cells = []
            max_lines = 1
            curr_font = font_header if is_header else font_body
            curr_size = size_header if is_header else size_body

            for c_idx, cell_text in enumerate(row_items):
                clean_cell = sanitize_text_for_pdf(cell_text)
                cell_w = col_widths[c_idx] - (2 * cell_padding_h)
                lines = self.wrap_text_precise(clean_cell, curr_font, curr_size, max_width=max(10.0, cell_w))
                wrapped_cells.append(lines)
                if len(lines) > max_lines:
                    max_lines = len(lines)

            row_h = (max_lines * line_height_body) + (2 * cell_padding_v)
            self.check_page_break(row_h + 5)

            y_top = self.y
            y_bottom = self.y - row_h

            # Fondo de la fila
            if is_header:
                self.current_page_stream.append(
                    f"0.12 0.16 0.23 rg {self.margin_x:.2f} {y_bottom:.2f} {avail_w:.2f} {row_h:.2f} re f"
                )
            elif is_even:
                self.current_page_stream.append(
                    f"0.97 0.98 0.99 rg {self.margin_x:.2f} {y_bottom:.2f} {avail_w:.2f} {row_h:.2f} re f"
                )

            # Rejilla / Bordes
            self.current_page_stream.append(f"0.80 0.83 0.88 RG 0.5 w")
            self.current_page_stream.append(
                f"{self.margin_x:.2f} {y_bottom:.2f} {avail_w:.2f} {row_h:.2f} re S"
            )

            # Líneas divisoras de columnas
            curr_x = self.margin_x
            for c_idx in range(num_cols - 1):
                curr_x += col_widths[c_idx]
                self.current_page_stream.append(
                    f"{curr_x:.2f} {y_bottom:.2f} m {curr_x:.2f} {y_top:.2f} l S"
                )

            # Texto de las celdas
            curr_x = self.margin_x
            for c_idx, lines in enumerate(wrapped_cells):
                cell_w = col_widths[c_idx]
                text_color = "1 1 1 rg" if is_header else "0.1 0.1 0.1 rg"

                for line_i, line_str in enumerate(lines):
                    safe_line = line_str.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                    text_y = y_top - cell_padding_v - (line_i * line_height_body) - (curr_size * 0.75)
                    text_x = curr_x + cell_padding_h
                    self.current_page_stream.append(
                        f"{text_color} BT /{curr_font} {curr_size} Tf {text_x:.2f} {text_y:.2f} Td ({safe_line}) Tj ET"
                    )
                curr_x += cell_w

            self.y = y_bottom

        self.y -= 4
        render_single_row(header_cells, is_header=True)
        for row_i, data_row in enumerate(content_rows):
            render_single_row(data_row, is_header=False, is_even=(row_i % 2 == 1))
        self.y -= 8

    def render_markdown(self, md_text: str, title: str = ""):
        clean_title = sanitize_text_for_pdf(title).strip()
        if clean_title:
            self.add_wrapped_paragraph(clean_title.upper(), font="F2", size=13.0, line_height=17.0, align="center")
            self.add_separator_line()
            self.y -= 4

        raw_lines = md_text.split("\n")
        has_signatures = False
        idx = 0
        n_lines = len(raw_lines)

        while idx < n_lines:
            raw = raw_lines[idx]
            line = raw.strip()
            if not line:
                self.y -= 4
                idx += 1
                continue

            # Detectar inicio de tabla Markdown (| col1 | col2 |)
            if "|" in line and idx + 1 < n_lines and re.match(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$", raw_lines[idx + 1].strip()):
                table_lines = []
                while idx < n_lines and "|" in raw_lines[idx]:
                    t_line = raw_lines[idx].strip()
                    if t_line:
                        table_lines.append(t_line)
                    idx += 1
                if table_lines:
                    self.add_table(table_lines)
                continue

            if line.startswith("# "):
                h1_text = line[2:].strip()
                # Evitar duplicar el título principal si es idéntico al encabezado superior
                if clean_title and h1_text.upper() == clean_title.upper():
                    idx += 1
                    continue
                self.y -= 5
                self.add_wrapped_paragraph(h1_text, font="F2", size=12.0, line_height=15.5, align="center")
                self.add_separator_line()
                self.y -= 2
            elif line.startswith("## "):
                self.y -= 5
                self.add_wrapped_paragraph(line[3:].strip(), font="F2", size=11.0, line_height=14.5, align="left")
                self.y -= 2
            elif line.startswith("### "):
                self.y -= 3
                self.add_wrapped_paragraph(line[4:].strip(), font="F2", size=10.0, line_height=13.0, align="left")
                self.y -= 1
            elif line.startswith("---") or line.startswith("___") or line.startswith("***"):
                self.add_separator_line()
            elif line.startswith("* ") or line.startswith("- ") or line.startswith("+ "):
                self.add_wrapped_paragraph("* " + line[2:].strip(), font="F1", size=9.5, line_height=13.0, indent=12.0)
            elif re.match(r"^\d+\.\s", line):
                self.add_wrapped_paragraph(line, font="F1", size=9.5, line_height=13.0, indent=12.0)
            elif "FIRMA" in line.upper() and ("LOCATARIO" in line.upper() or "CLIENTE" in line.upper() or "PARTE" in line.upper() or "CONFORMIDAD" in line.upper()):
                has_signatures = True
            else:
                self.add_wrapped_paragraph(line, font="F1", size=9.5, line_height=13.0)

            idx += 1

        if has_signatures:
            self.add_signatures()

    def build_pdf(self) -> bytes:
        if self.current_page_stream:
            self.pages.append(self.current_page_stream)
            self.current_page_stream = []

        total_pages = max(1, len(self.pages))

        for idx, p_stream in enumerate(self.pages):
            p_num = idx + 1
            footer_str = f"{self.footer_text}  |  Pagina {p_num} de {total_pages}"
            p_stream.append(f"0.3 w 0.8 0.8 0.8 RG {self.margin_x:.2f} {self.margin_y:.2f} m {self.width - self.margin_x:.2f} {self.margin_y:.2f} l S")
            p_stream.append(f"BT /F1 8 Tf {self.margin_x:.2f} {self.margin_y - 12:.2f} Td ({footer_str}) Tj ET")

        objs = ["", "", ""]
        def add_obj(content):
            objs.append(content)
            return len(objs)

        catalog_id = 1
        pages_id = 3
        page_ids = []

        f1_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        f3_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding /WinAnsiEncoding >>")
        f4_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold /Encoding /WinAnsiEncoding >>")

        font_dict = f"<< /F1 {f1_id} 0 R /F2 {f2_id} 0 R /F3 {f3_id} 0 R /F4 {f4_id} 0 R >>"

        for p_stream in self.pages:
            stream_data = "\n".join(p_stream).encode("latin-1", "replace")
            compressed = zlib.compress(stream_data)
            c_id = add_obj(f"<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode("latin-1") + compressed + b"\nendstream")
            p_id = add_obj(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {self.width} {self.height}] /Contents {c_id} 0 R /Resources << /Font {font_dict} >> >>")
            page_ids.append(p_id)

        objs[0] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
        objs[1] = "<< /Type /Outlines /Count 0 >>"
        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, obj in enumerate(objs):
            offsets.append(out.tell())
            if isinstance(obj, bytes):
                out.write(f"{i+1} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n")
            else:
                out.write(f"{i+1} 0 obj\n{obj}\nendobj\n".encode("latin-1"))

        xref_pos = out.tell()
        out.write(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode("latin-1"))
        for off in offsets:
            out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
        out.write(f"trailer\n<< /Size {len(objs)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
        return out.getvalue()


def cleanup_old_pdfs(max_age_hours: int = 24):
    """Elimina automáticamente archivos PDF temporales que tengan más de max_age_hours de antigüedad."""
    try:
        import time
        now = time.time()
        max_age_sec = max_age_hours * 3600
        if os.path.exists(PDF_STORAGE_DIR):
            for fname in os.listdir(PDF_STORAGE_DIR):
                if fname.endswith(".pdf"):
                    fpath = os.path.join(PDF_STORAGE_DIR, fname)
                    if os.path.isfile(fpath):
                        file_age = now - os.path.getmtime(fpath)
                        if file_age > max_age_sec:
                            try:
                                os.remove(fpath)
                            except Exception:
                                pass
    except Exception as e:
        import sys
        print(f"⚠️ Error limpiando PDFs antiguos: {e}", file=sys.stderr)


def create_pdf_from_markdown(
    title: str,
    markdown_content: str,
    filename: Optional[str] = None,
    company_name: str = "Teccam S.R.L.",
    base_url: str = "http://127.0.0.1:8000"
) -> Dict[str, Any]:
    """Genera un archivo PDF, lo guarda en disco para descarga directa y devuelve metadata + URL."""
    cleanup_old_pdfs(max_age_hours=24)

    clean_title = (title or "").strip()
    if not clean_title and markdown_content:
        for line in markdown_content.strip().split("\n"):
            if line.startswith("#"):
                clean_title = line.lstrip("#").strip()
                break
    if not clean_title:
        clean_title = "Documento Oficial"

    clean_filename = filename.strip() if filename else f"{re.sub(r'[^a-zA-Z0-9_-]', '_', clean_title.lower())}.pdf"
    if not clean_filename.lower().endswith(".pdf"):
        clean_filename += ".pdf"

    builder = PDFDocumentBuilder(company_name=company_name)
    builder.render_markdown(markdown_content, title=clean_title)
    pdf_bytes = builder.build_pdf()

    file_id = uuid.uuid4().hex[:12]
    saved_name = f"{file_id}_{clean_filename}"
    file_path = os.path.join(PDF_STORAGE_DIR, saved_name)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    size_kb = round(len(pdf_bytes) / 1024, 1)
    page_count = len(builder.pages)

    download_url = f"{base_url.rstrip('/')}/api/tools/pdf/download/{file_id}/{clean_filename}"

    formatted_card = f"""✅ Archivo PDF compilado exitosamente.

Enlace de descarga para el usuario:
[📥 Descargar {clean_filename}]({download_url})

Detalles:
* Archivo: `{clean_filename}` ({page_count} páginas, {size_kb} KB)
* Título: {clean_title}
"""
    return {
        "success": True,
        "title": clean_title,
        "filename": clean_filename,
        "file_id": file_id,
        "file_path": file_path,
        "download_url": download_url,
        "pages": page_count,
        "size_kb": size_kb,
        "formatted_context": formatted_card,
        "text": formatted_card
    }
