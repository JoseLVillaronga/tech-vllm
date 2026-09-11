"""
rag_engine.py - Wrapper de compatibilidad hacia atrás para el subsistema RAG modularizado.

Este módulo re-exporta todos los componentes, funciones y constantes desde el nuevo paquete `rag/`,
garantizando 100% de compatibilidad hacia atrás con endpoints, herramientas del gateway y tests unitarios.
"""

from rag import *
from rag import __all__

__all__ = list(__all__)
