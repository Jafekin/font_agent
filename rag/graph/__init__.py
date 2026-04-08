"""rag.graph — GraphRAG 模块（知识图谱构建与检索）."""

from .client import Neo4jClient
from .builder import GraphBuilder
from .retriever import GraphRetriever, GraphSearchResult
from .models import Collection, Document, Edition, Entity, Layout, Page

__version__ = "2.0.0"

__all__ = [
    "Neo4jClient",
    "GraphBuilder",
    "GraphRetriever",
    "GraphSearchResult",
    "Document",
    "Edition",
    "Collection",
    "Page",
    "Layout",
    "Entity",
]
