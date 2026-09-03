import time
import json
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse


async def handle_rag_search(request: Request, body: bytes) -> JSONResponse:
    """
    Manejador para el endpoint POST /api/tools/rag-search y /v1/rag/search conectando con LanceDB.
    """
    try:
        from rag_engine import search_knowledge_base, format_rag_context_for_llm, get_rag_settings

        rag_sett = get_rag_settings()
        if not rag_sett.get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El servicio de Base de Conocimiento RAG está desactivado globalmente en la suite."
            )

        body_data = json.loads(body) if body else {}
        query = body_data.get("query", "").strip()
        tema = body_data.get("tema") or None
        temas = body_data.get("temas") or None
        doc_id = body_data.get("doc_id") or body_data.get("documento_id") or None
        vigencia = body_data.get("vigencia") or None
        solo_vigentes = bool(body_data.get("solo_vigentes", False))
        top_k = int(body_data.get("top_k", 5))

        if not query:
            raise HTTPException(status_code=400, detail="El parámetro 'query' no puede estar vacío.")

        t_rag_0 = time.time()
        results = search_knowledge_base(
            query=query,
            tema=tema,
            temas=temas,
            doc_id=doc_id,
            vigencia=vigencia,
            solo_vigentes=solo_vigentes,
            top_k=top_k
        )
        dur_rag_ms = round((time.time() - t_rag_0) * 1000, 2)
        context_str = format_rag_context_for_llm(results)

        return JSONResponse(content={
            "query": query,
            "tema": tema,
            "temas": temas,
            "doc_id": doc_id,
            "vigencia": vigencia,
            "solo_vigentes": solo_vigentes,
            "results_count": len(results),
            "latency_ms": dur_rag_ms,
            "context": context_str,
            "results": results
        })
    except HTTPException:
        raise
    except Exception as re:
        raise HTTPException(status_code=500, detail=f"Error en búsqueda RAG: {str(re)}")


async def handle_rag_document(request: Request, body: bytes) -> JSONResponse:
    """
    Manejador para el endpoint POST /api/tools/rag-document y /v1/rag/document para lectura de documento completo o paginado.
    """
    try:
        from rag_engine import get_document_full_content, get_rag_settings

        rag_sett = get_rag_settings()
        if not rag_sett.get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El servicio de Base de Conocimiento RAG está desactivado globalmente en la suite."
            )

        body_data = json.loads(body) if body else {}
        doc_id = body_data.get("doc_id", "").strip()
        parte = int(body_data.get("parte", 1))
        token_threshold = int(body_data.get("token_threshold", 60000))
        chunk_threshold = body_data.get("chunk_threshold")
        chunk_threshold_val = int(chunk_threshold) if chunk_threshold is not None else None
        seccion = body_data.get("seccion") or body_data.get("section") or None

        if not doc_id:
            raise HTTPException(status_code=400, detail="El parámetro 'doc_id' es obligatorio para leer el documento.")

        t_doc_0 = time.time()
        res = get_document_full_content(
            doc_id=doc_id,
            parte=parte,
            token_threshold=token_threshold,
            chunk_threshold=chunk_threshold_val,
            seccion=seccion
        )
        dur_doc_ms = round((time.time() - t_doc_0) * 1000, 2)

        if not res.get("success", False):
            raise HTTPException(status_code=404, detail=res.get("error", "Error recuperando documento."))

        return JSONResponse(content={
            "success": True,
            "doc_id": res.get("doc_id"),
            "titulo": res.get("titulo"),
            "tema": res.get("tema"),
            "autor": res.get("autor"),
            "seccion_solicitada": res.get("seccion_solicitada"),
            "seccion_nombre": res.get("seccion_nombre"),
            "total_chunks": res.get("total_chunks"),
            "total_doc_tokens": res.get("total_doc_tokens"),
            "tokens_en_esta_parte": res.get("tokens_en_esta_parte"),
            "modo": res.get("modo"),
            "parte_actual": res.get("parte_actual", 1),
            "total_partes": res.get("total_partes", 1),
            "chunks_en_esta_parte": res.get("chunks_en_esta_parte", res.get("total_chunks")),
            "latency_ms": dur_doc_ms,
            "content": res.get("content", "")
        })
    except HTTPException:
        raise
    except Exception as de:
        raise HTTPException(status_code=500, detail=f"Error al leer documento RAG: {str(de)}")


async def handle_rag_structure(request: Request, body: bytes) -> JSONResponse:
    """
    Manejador para el endpoint POST /api/tools/rag-structure y /v1/rag/structure (GPS Documental).
    """
    try:
        from rag_engine import get_document_structure, get_rag_settings

        rag_sett = get_rag_settings()
        if not rag_sett.get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El servicio de Base de Conocimiento RAG está desactivado globalmente en la suite."
            )

        body_data = json.loads(body) if body else {}
        doc_id = body_data.get("doc_id", "").strip()
        filtro = body_data.get("filtro") or None

        if not doc_id:
            raise HTTPException(status_code=400, detail="El parámetro 'doc_id' es obligatorio para consultar la estructura.")

        t_struct_0 = time.time()
        res = get_document_structure(doc_id=doc_id, filtro=filtro)
        dur_struct_ms = round((time.time() - t_struct_0) * 1000, 2)

        if not res.get("success", False):
            raise HTTPException(status_code=404, detail=res.get("error", "Error consultando estructura del documento."))

        return JSONResponse(content={
            "success": True,
            "doc_id": res.get("doc_id"),
            "titulo": res.get("titulo"),
            "tema": res.get("tema"),
            "autor": res.get("autor"),
            "total_chunks": res.get("total_chunks"),
            "total_doc_tokens": res.get("total_doc_tokens"),
            "sections_count": res.get("sections_count", 0),
            "sections": res.get("sections", []),
            "latency_ms": dur_struct_ms,
            "content": res.get("content", "")
        })
    except HTTPException:
        raise
    except Exception as se:
        raise HTTPException(status_code=500, detail=f"Error al consultar estructura RAG: {str(se)}")


async def handle_rag_library_index(request: Request, body: bytes = b"") -> JSONResponse:
    """
    Manejador para el endpoint POST /api/tools/rag-library-index y GET/POST /v1/rag/library-index.
    Retorna el Mapa Ontológico Global y el árbol jerárquico de toda la biblioteca disponible.
    """
    try:
        from rag_engine import get_library_index, get_rag_settings

        rag_sett = get_rag_settings()
        if not rag_sett.get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="El servicio de Base de Conocimiento RAG está desactivado globalmente en la suite."
            )

        body_data = {}
        if body:
            try:
                body_data = json.loads(body)
            except Exception:
                pass

        # Parámetros desde query params si fue GET o desde body si fue POST
        query_params = request.query_params
        solo_vigentes = body_data.get("solo_vigentes")
        if solo_vigentes is None:
            solo_vigentes = query_params.get("solo_vigentes", "false").lower() in ("true", "1", "yes")
        else:
            solo_vigentes = bool(solo_vigentes)

        tema = body_data.get("tema") or query_params.get("tema") or None

        t0 = time.time()
        res = get_library_index(solo_vigentes=solo_vigentes, tema=tema)
        dur_ms = round((time.time() - t0) * 1000, 2)

        if not res.get("success", False):
            raise HTTPException(status_code=500, detail=res.get("error", "Error generando índice de biblioteca."))

        return JSONResponse(content={
            "success": True,
            "total_documents": res.get("total_documents", 0),
            "total_chunks": res.get("total_chunks", 0),
            "total_tokens": res.get("total_tokens", 0),
            "domains_count": res.get("domains_count", 0),
            "domains": res.get("domains", {}),
            "latency_ms": dur_ms,
            "content": res.get("content", "")
        })
    except HTTPException:
        raise
    except Exception as ie:
        raise HTTPException(status_code=500, detail=f"Error al obtener índice de biblioteca RAG: {str(ie)}")

