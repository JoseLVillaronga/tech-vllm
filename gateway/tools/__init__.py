"""
Módulo de micro-routers para herramientas desacopladas del Gateway.
"""
from gateway.tools.web_search import handle_web_search, perform_ollama_web_search
from gateway.tools.pdf_generator import handle_pdf_generation, handle_pdf_download
from gateway.tools.doc_reader import handle_doc_reader
from gateway.tools.rag_endpoints import handle_rag_search, handle_rag_document, handle_rag_structure

__all__ = [
    "handle_web_search",
    "perform_ollama_web_search",
    "handle_pdf_generation",
    "handle_pdf_download",
    "handle_doc_reader",
    "handle_rag_search",
    "handle_rag_document",
    "handle_rag_structure"
]
