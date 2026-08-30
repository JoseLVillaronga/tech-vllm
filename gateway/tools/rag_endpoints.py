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
        top_k = int(body_data.get("top_k", 5))

        if not query:
            raise HTTPException(status_code=400, detail="El parámetro 'query' no puede estar vacío.")

        t_rag_0 = time.time()
        results = search_knowledge_base(query=query, tema=tema, temas=temas, top_k=top_k)
        dur_rag_ms = round((time.time() - t_rag_0) * 1000, 2)
        context_str = format_rag_context_for_llm(results)

        return JSONResponse(content={
            "query": query,
            "tema": tema,
            "temas": temas,
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

        if not doc_id:
            raise HTTPException(status_code=400, detail="El parámetro 'doc_id' es obligatorio para leer el documento.")

        t_doc_0 = time.time()
        res = get_document_full_content(
            doc_id=doc_id,
            parte=parte,
            token_threshold=token_threshold,
            chunk_threshold=chunk_threshold_val
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
