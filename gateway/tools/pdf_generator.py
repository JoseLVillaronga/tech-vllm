import os
import sys
import json
import time
from fastapi import Request, Response, HTTPException
from fastapi.responses import FileResponse


def handle_pdf_download(file_id: str, dl_filename: str):
    """
    Descarga pública o autenticada de archivos PDF generados con auto-limpieza TTL.
    """
    try:
        storage_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "outputs", "pdfs")
        matched_file = None

        if os.path.exists(storage_dir):
            now_ts = time.time()
            for fname in os.listdir(storage_dir):
                fpath = os.path.join(storage_dir, fname)
                try:
                    # Limpieza automática de PDFs antiguos (> 24 horas)
                    if os.path.isfile(fpath) and (now_ts - os.path.getmtime(fpath) > 86400):
                        os.remove(fpath)
                        continue
                except Exception:
                    pass

                if fname.startswith(f"{file_id}_"):
                    matched_file = os.path.join(storage_dir, fname)
                    break

        if not matched_file or not os.path.exists(matched_file):
            raise HTTPException(status_code=404, detail="El documento PDF solicitado no existe o ha expirado.")

        return FileResponse(
            path=matched_file,
            media_type="application/pdf",
            filename=dl_filename,
            headers={"Content-Disposition": f'attachment; filename="{dl_filename}"'}
        )
    except HTTPException:
        raise
    except Exception as dl_err:
        raise HTTPException(status_code=500, detail=f"Error al descargar PDF: {dl_err}")


async def handle_pdf_generation(request: Request, gateway_port: int = 8000) -> Response:
    """
    Manejador para el endpoint POST /api/tools/generate-pdf.
    """
    try:
        from pdf_engine import create_pdf_from_markdown

        tool_body = await request.body()
        tool_data = json.loads(tool_body) if tool_body else {}

        # Manejar inputs directos o empaquetados en 'arguments'
        if "arguments" in tool_data and isinstance(tool_data["arguments"], dict):
            tool_data.update(tool_data["arguments"])
        elif "arguments" in tool_data and isinstance(tool_data["arguments"], str):
            try:
                arg_obj = json.loads(tool_data["arguments"])
                if isinstance(arg_obj, dict):
                    tool_data.update(arg_obj)
            except Exception:
                pass

        title = tool_data.get("title") or tool_data.get("document_title") or "Documento Oficial"
        markdown_content = (
            tool_data.get("markdown_content")
            or tool_data.get("content")
            or tool_data.get("text")
            or tool_data.get("markdown")
            or ""
        )
        filename = tool_data.get("filename") or tool_data.get("file_name") or None
        company_name = tool_data.get("company_name") or "Documento Oficial"

        if not markdown_content:
            return Response(
                content=json.dumps({"success": False, "error": "El parámetro 'markdown_content' no puede estar vacío."}),
                media_type="application/json",
                status_code=400
            )

        # Construir base_url usando la cabecera Host de la petición entrante
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
        host_hdr = request.headers.get("host") or f"127.0.0.1:{gateway_port}"
        base_url = f"{proto}://{host_hdr}"

        pdf_res = create_pdf_from_markdown(
            title=title,
            markdown_content=markdown_content,
            filename=filename,
            company_name=company_name,
            base_url=base_url
        )

        return Response(
            content=json.dumps(pdf_res),
            media_type="application/json",
            status_code=200
        )
    except Exception as pdf_err:
        print(f"⚠️ Error procesando tool de generación de PDF: {pdf_err}", file=sys.stderr, flush=True)
        return Response(
            content=json.dumps({"success": False, "error": str(pdf_err)}),
            media_type="application/json",
            status_code=500
        )
