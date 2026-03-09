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

__version__ = "1.0.0"

__all__ = [
    # 客户端
    "Neo4jClient",
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
