#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Generación de Documentos y Contratos en PDF para vLLM Suite Gateway.
Genera documentos PDF estándar A4 sin dependencias externas pesadas.
"""

import io
import zlib
import re
import base64
from typing import Optional, Dict, Any, List


class PDFDocumentBuilder:
    """Compilador de documentos PDF A4 en memoria con soporte de Markdown."""

    def __init__(self, page_size=(595.28, 841.89), company_name: str = "Documento Oficial"):
        self.width, self.height = page_size
        self.margin_x = 54.0  # ~1.9 cm
        self.margin_y = 54.0
        self.printable_width = self.width - 2 * self.margin_x
        self.pages = []
        self.current_page_stream = []
        self.y = self.height - self.margin_y
        self.footer_text = company_name

    def new_page(self):
        if self.current_page_stream or not self.pages:
            self.pages.append(self.current_page_stream)
            self.current_page_stream = []
        self.y = self.height - self.margin_y

    def check_page_break(self, needed_height: float):
        if self.y - needed_height < self.margin_y + 35:
            self.new_page()

    def wrap_text(self, text: str, font: str = "F1", size: float = 10.5) -> List[str]:
        char_width = size * 0.50
        max_chars = max(10, int(self.printable_width / char_width))
        words = text.split(" ")
        lines = []
        current_line = []
        current_len = 0
        for word in words:
            if not word:
                continue
            word_len = len(word)
            if current_len + word_len + (1 if current_line else 0) <= max_chars:
                current_line.append(word)
                current_len += word_len + (1 if len(current_line) > 1 else 0)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_len = word_len
        if current_line:
            lines.append(" ".join(current_line))
        return lines if lines else [""]

    def add_wrapped_paragraph(self, text: str, font: str = "F1", size: float = 10.5, line_height: float = 14.0, align: str = "left", indent: float = 0.0):
        clean = text
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)
        clean = re.sub(r"\*(.*?)\*", r"\1", clean)
        clean = re.sub(r"`(.*?)`", r"\1", clean)
        
        lines = self.wrap_text(clean, font, size)
        for i, line in enumerate(lines):
            self.check_page_break(line_height)
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            x = self.margin_x + (indent if i == 0 else 0)
            if align == "center":
                approx_w = len(line) * size * 0.50
                x = max(self.margin_x, (self.width - approx_w) / 2)
            elif align == "right":
                approx_w = len(line) * size * 0.50
                x = max(self.margin_x, self.width - self.margin_x - approx_w)
                
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
        lbl_l = name_left.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lbl_r = name_right.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        
        self.current_page_stream.append(f"BT /F1 8.5 Tf {x_left_start:.2f} {self.y:.2f} Td ({lbl_l}) Tj ET")
        self.current_page_stream.append(f"BT /F1 8.5 Tf {x_right_start:.2f} {self.y:.2f} Td ({lbl_r}) Tj ET")
        self.y -= 15

    def render_markdown(self, md_text: str, title: str = ""):
        if not self.pages:
            self.new_page()
            
        if title:
            self.add_wrapped_paragraph(title.upper(), font="F2", size=14, line_height=18, align="center")
            self.add_separator_line()
            self.y -= 8
            
        raw_lines = md_text.split("\n")
        has_signatures = False
        
        for raw in raw_lines:
            line = raw.strip()
            if not line:
                self.y -= 5
                continue
                
            if line.startswith("# "):
                self.y -= 6
                self.add_wrapped_paragraph(line[2:], font="F2", size=13, line_height=16, align="center")
                self.add_separator_line()
                self.y -= 3
            elif line.startswith("## "):
                self.y -= 5
                self.add_wrapped_paragraph(line[3:], font="F2", size=11.5, line_height=15, align="left")
                self.y -= 2
            elif line.startswith("### "):
                self.y -= 3
                self.add_wrapped_paragraph(line[4:], font="F2", size=10.5, line_height=13.5, align="left")
                self.y -= 2
            elif line.startswith("---") or line.startswith("___") or line.startswith("***"):
                self.add_separator_line()
            elif line.startswith("* ") or line.startswith("- ") or line.startswith("+ "):
                self.add_wrapped_paragraph("• " + line[2:], font="F1", size=10, line_height=13, indent=12.0)
            elif re.match(r"^\d+\.\s", line):
                self.add_wrapped_paragraph(line, font="F1", size=10, line_height=13, indent=12.0)
            elif "FIRMA" in line.upper() and ("LOCATARIO" in line.upper() or "CLIENTE" in line.upper() or "PARTE" in line.upper() or "CONFORMIDAD" in line.upper()):
                has_signatures = True
            else:
                self.add_wrapped_paragraph(line, font="F1", size=10, line_height=13.5)
                
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


def create_pdf_from_markdown(
    title: str,
    markdown_content: str,
    filename: Optional[str] = None,
    company_name: str = "Documento Oficial"
) -> Dict[str, Any]:
    """Genera un archivo PDF a partir de Markdown y devuelve metadata + Base64."""
    clean_title = title.strip() or "Documento"
    clean_filename = filename.strip() if filename else f"{re.sub(r"[^a-zA-Z0-9_-]", "_", clean_title.lower())}.pdf"
    if not clean_filename.lower().endswith(".pdf"):
        clean_filename += ".pdf"
        
    builder = PDFDocumentBuilder(company_name=company_name)
    builder.render_markdown(markdown_content, title=clean_title)
    pdf_bytes = builder.build_pdf()
    
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    data_uri = f"data:application/pdf;base64,{b64_pdf}"
    size_kb = round(len(pdf_bytes) / 1024, 1)
    page_count = len(builder.pages)
    
    formatted_card = f"""
### 📄 Documento PDF Generado Exitosamente

* **Título:** {clean_title}
* **Archivo:** `{clean_filename}`
* **Páginas:** {page_count}
* **Tamaño:** {size_kb} KB

---

[📥 **Descargar {clean_filename}**]({data_uri})

<div style="margin: 15px 0; padding: 14px; background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 10px; display: flex; align-items: center; justify-content: space-between;">
    <div>
        <span style="font-weight: bold; color: #6366f1; font-size: 14px;">📄 {clean_filename}</span>
        <div style="font-size: 12px; color: #94a3b8;">Documento PDF compilado ({page_count} pág, {size_kb} KB)</div>
    </div>
    <a href="{data_uri}" download="{clean_filename}" style="background: #4f46e5; color: white; padding: 8px 18px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 13px; display: inline-block;">
        📥 Descargar PDF
    </a>
</div>
"""
    return {
        "success": True,
        "title": clean_title,
        "filename": clean_filename,
        "pages": page_count,
        "size_kb": size_kb,
        "data_uri": data_uri,
        "formatted_context": formatted_card,
        "text": formatted_card
    }
