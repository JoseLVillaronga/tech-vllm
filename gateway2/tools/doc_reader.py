import os
import sys
import json
import base64
import httpx
from fastapi import Request, Response


async def handle_doc_reader(request: Request) -> Response:
    """
    Manejador para el endpoint POST /api/tools/read-file conectado a Docling Serve (:5020).
    Soporta subidas multipart/form-data y payloads JSON con rutas locales, URLs o base64.
    """
    try:
        content_type = request.headers.get("content-type", "")
        docling_url = os.getenv("DOCLING_URL", "http://127.0.0.1:5020/v1/convert/file")
        extracted_md = ""
        filename = "documento"

        # Caso A: Subida directa de archivo (multipart/form-data)
        if "multipart/form-data" in content_type:
            form = await request.form()
            upload_file = form.get("file") or form.get("files") or form.get("document")
            if upload_file:
                filename = upload_file.filename or "documento"
                file_bytes = await upload_file.read()

                files_payload = {"files": (filename, file_bytes, upload_file.content_type or "application/octet-stream")}
                async with httpx.AsyncClient(timeout=45.0) as client:
                    d_resp = await client.post(docling_url, files=files_payload)
                    if d_resp.status_code == 200:
                        d_json = d_resp.json()
                        doc_obj = d_json.get("document", {})
                        if isinstance(doc_obj, dict):
                            extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""
                    else:
                        return Response(
                            content=json.dumps({"success": False, "error": f"Docling Serve respondió HTTP {d_resp.status_code}: {d_resp.text}"}),
                            media_type="application/json",
                            status_code=502
                        )
        # Caso B: JSON con 'file_path', 'url', 'base64'
        else:
            tool_body = await request.body()
            tool_data = json.loads(tool_body) if tool_body else {}
            if "arguments" in tool_data and isinstance(tool_data["arguments"], dict):
                tool_data.update(tool_data["arguments"])
            elif "arguments" in tool_data and isinstance(tool_data["arguments"], str):
                try:
                    arg_obj = json.loads(tool_data["arguments"])
                    if isinstance(arg_obj, dict):
                        tool_data.update(arg_obj)
                except Exception:
                    pass

            file_path = tool_data.get("file_path") or tool_data.get("path")
            file_url = tool_data.get("url")
            base64_data = tool_data.get("base64")
            filename = tool_data.get("filename") or "documento"

            if file_path and os.path.exists(file_path):
                filename = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                files_payload = {"files": (filename, file_bytes, "application/octet-stream")}
                async with httpx.AsyncClient(timeout=45.0) as client:
                    d_resp = await client.post(docling_url, files=files_payload)
                    if d_resp.status_code == 200:
                        d_json = d_resp.json()
                        doc_obj = d_json.get("document", {})
                        if isinstance(doc_obj, dict):
                            extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""
            elif file_url:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    src_resp = await client.get(file_url)
                    if src_resp.status_code == 200:
                        filename = os.path.basename(file_url.split("?")[0]) or "documento.pdf"
                        files_payload = {"files": (filename, src_resp.content, "application/octet-stream")}
                        d_resp = await client.post(docling_url, files=files_payload)
                        if d_resp.status_code == 200:
                            d_json = d_resp.json()
                            doc_obj = d_json.get("document", {})
                            if isinstance(doc_obj, dict):
                                extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""
            elif base64_data:
                file_bytes = base64.b64decode(base64_data)
                files_payload = {"files": (filename, file_bytes, "application/octet-stream")}
                async with httpx.AsyncClient(timeout=45.0) as client:
                    d_resp = await client.post(docling_url, files=files_payload)
                    if d_resp.status_code == 200:
                        d_json = d_resp.json()
                        doc_obj = d_json.get("document", {})
                        if isinstance(doc_obj, dict):
                            extracted_md = doc_obj.get("md_content") or doc_obj.get("text_content") or ""

        if not extracted_md:
            return Response(
                content=json.dumps({"success": False, "error": "No se pudo extraer contenido del documento o el archivo está vacío."}),
                media_type="application/json",
                status_code=400
            )

        response_payload = {
            "success": True,
            "filename": filename,
            "length_chars": len(extracted_md),
            "markdown_content": extracted_md,
            "content": extracted_md
        }
        return Response(
            content=json.dumps(response_payload),
            media_type="application/json",
            status_code=200
        )
    except Exception as e:
        print(f"⚠️ Error al procesar lectura de archivo en Gateway: {e}", file=sys.stderr, flush=True)
        return Response(
            content=json.dumps({"success": False, "error": str(e)}),
            media_type="application/json",
            status_code=500
        )
