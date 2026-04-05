"""现代RAG系统配置管理."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os


@dataclass
class ModelConfig:
    """模型配置."""

    # 视觉编码器 (Qwen2-VL 或 Chinese-CLIP)
    vision_model: str = "OFA-Sys/chinese-clip-vit-large-patch14-336px"
    # vision_model: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    vision_device: str = "cuda"
    vision_batch_size: int = 8

    # 文本编码器 (SikuBERT 或 RoBERTa)
    text_model: str = "SIKU-BERT/sikubert"
    text_device: str = "cuda"
    text_batch_size: int = 32

    # 重排序模型
    reranker_model: str = "BAAI/bge-reranker-large"
    reranker_device: str = "cuda"

    # LLM (用于推理和生成)
    llm_model: str = "ernie-4.5-turbo-vl"
    llm_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    llm_base_url: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL"))


@dataclass
class RetrieverConfig:
    """检索器配置."""

    # 向量检索
    vector_top_k: int = 50
    vector_similarity_threshold: float = 0.7

    # 文本检索
    text_top_k: int = 30
    text_min_score: float = 5.0

    # 图谱检索
    graph_max_depth: int = 2
    graph_top_k: int = 20

    # 混合检索
    hybrid_top_k: int = 10
    fusion_weights: dict = field(default_factory=lambda: {
        "vector": 0.4,
        "text": 0.3,
        "graph": 0.3
    })


@dataclass
class IndexConfig:
    """索引配置."""

    # Milvus向量数据库
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "ancient_manuscripts"

    # Elasticsearch文本索引
    es_host: str = "localhost"
    es_port: int = 9200
    es_index: str = "manuscripts_text"

    # Neo4j图数据库
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"


@dataclass
class PipelineConfig:
    """流程配置."""

    # 多阶段推理
    enable_multi_stage: bool = True
    stages: list = field(default_factory=lambda: [
        "version_detection",
        "dating_inference",
        "layout_analysis",
        "content_analysis",
        "catalog_generation"
    ])

    # 知识融合
    enable_fusion: bool = True
    fusion_method: str = "attention"  # attention, weighted, concat

    # 输出验证
    enable_validation: bool = True
    min_confidence: float = 0.6


@dataclass
class ModernRAGConfig:
    """现代RAG系统总配置."""

    # 项目路径
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = field(default_factory=lambda: Path("outputs"))
    index_dir: Path = field(default_factory=lambda: Path("rag/modern/indexes"))
    cache_dir: Path = field(default_factory=lambda: Path("rag/modern/cache"))

    # 子配置
    model: ModelConfig = field(default_factory=ModelConfig)
    retriever: RetrieverConfig = field(default_factory=RetrieverConfig)
    index: IndexConfig = field(default_factory=IndexConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)

    def __post_init__(self):
        """确保目录存在."""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


# 全局配置实例
config = ModernRAGConfig()
