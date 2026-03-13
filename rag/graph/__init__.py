"""图谱模块初始化."""

from .models import (
    Collection,
    Document,
    Edition,
    Entity,
    Layout,
    Page,
    Seal,
    Volume,
)
from .neo4j_client import Neo4jClient
from .builder import GraphBuilder
from .enhanced_builder import EnhancedGraphBuilder
from .data_loader import OutputsDataLoader
from .query_interface import GraphQueryInterface
from .retriever import GraphRetriever, GraphSearchResult
from .explainer import EvidenceExplainer

__version__ = "1.0.0"

__all__ = [
    # 客户端
    "Neo4jClient",
    # 构建器
    "GraphBuilder",
    "EnhancedGraphBuilder",
    "OutputsDataLoader",
    # 查询接口
    "GraphQueryInterface",
    "GraphRetriever",
    "GraphSearchResult",
    "EvidenceExplainer",
    # 数据模型
    "Document",
    "Volume",
    "Page",
    "Edition",
    "Collection",
    "Layout",
    "Seal",
    "Entity",
]
