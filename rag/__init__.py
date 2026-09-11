"""
rag - Subsistema RAG modularizado para vLLM Suite.
Implementa arquitectura RAG desacoplada bajo las Leyes de Ingeniería 1, 3 y 4.
"""

from .config import (
    PROJECT_DIR,
    LANCEDB_DIR,
    TABLE_NAME,
    EMBEDDINGS_BACKEND_PORT,
    MASTER_KEY,
    get_mongo_uri,
    MONGO_DB,
    TECCAM_PDF_URL_BASE,
    TECCAM_PDF_API_KEY,
)

from .db import (
    get_lancedb,
    get_table,
    get_canonical_rag_schema,
    list_knowledge_bases,
    create_knowledge_base,
    clone_knowledge_domain,
    delete_knowledge_base,
    get_rag_stats,
)

from .settings import (
    get_mongo_db,
    get_rag_settings,
    save_rag_settings,
)

from .embeddings import (
    generate_embedding,
    generate_embeddings_batch,
)

from .matching import (
    normalize_text,
    build_boundary_regex,
    match_section_query,
    find_documents_by_fuzzy_title,
)

from .search import (
    search_knowledge_base,
    format_rag_context_for_llm,
)

from .reader import (
    fetch_teccam_document_raw,
    get_document_structure,
    _partition_chunks_dynamically,
    get_document_full_content,
    get_library_index,
)

__all__ = [
    # config
    "PROJECT_DIR",
    "LANCEDB_DIR",
    "TABLE_NAME",
    "EMBEDDINGS_BACKEND_PORT",
    "MASTER_KEY",
    "get_mongo_uri",
    "MONGO_DB",
    "TECCAM_PDF_URL_BASE",
    "TECCAM_PDF_API_KEY",
    # db
    "get_lancedb",
    "get_table",
    "get_canonical_rag_schema",
    "list_knowledge_bases",
    "create_knowledge_base",
    "clone_knowledge_domain",
    "delete_knowledge_base",
    "get_rag_stats",
    # settings
    "get_mongo_db",
    "get_rag_settings",
    "save_rag_settings",
    # embeddings
    "generate_embedding",
    "generate_embeddings_batch",
    # matching
    "normalize_text",
    "build_boundary_regex",
    "match_section_query",
    "find_documents_by_fuzzy_title",
    # search
    "search_knowledge_base",
    "format_rag_context_for_llm",
    # reader
    "fetch_teccam_document_raw",
    "get_document_structure",
    "_partition_chunks_dynamically",
    "get_document_full_content",
    "get_library_index",
]
