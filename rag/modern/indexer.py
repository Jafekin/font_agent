"""索引构建器 - 从outputs目录构建多模态索引."""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import numpy as np
from tqdm import tqdm

from .config import ModernRAGConfig
from .encoders import VisionEncoder, TextEncoder

logger = logging.getLogger(__name__)


class ModernIndexer:
    """现代索引构建器."""

    def __init__(self, config: Optional[ModernRAGConfig] = None):
        """初始化索引构建器.

        Args:
            config: 配置对象
        """
        self.config = config or ModernRAGConfig()
        self.vision_encoder = None
        self.text_encoder = None

    def build_index(self, data_dir: Path, output_dir: Path):
        """构建索引.

        Args:
            data_dir: 数据目录（outputs/）
            output_dir: 输出目录
        """
        logger.info(f"开始构建索引: {data_dir} -> {output_dir}")

        # 初始化编码器
        self.vision_encoder = VisionEncoder(
            model_name=self.config.model.vision_model,
            device=self.config.model.vision_device
        )
        self.text_encoder = TextEncoder(
            model_name=self.config.model.text_model,
            device=self.config.model.text_device
        )

        # 扫描数据目录
        page_dirs = [d for d in Path(data_dir).iterdir() if d.is_dir()]
        logger.info(f"找到 {len(page_dirs)} 个页面目录")

        # 构建索引数据
        embeddings = []
        ids = []
        metadata_list = []

        for page_dir in tqdm(page_dirs, desc="构建索引"):
            try:
                page_data = self._load_page_data(page_dir)
                if page_data is None:
                    continue

                # 编码图像
                image_path = page_data.get("image_path")
                if not image_path or not Path(image_path).exists():
                    logger.warning(f"图像不存在: {image_path}")
                    continue

                image_embedding = self.vision_encoder.encode_image(image_path)

                # 编码文本（用于 metadata，不参与向量拼接以保持维度一致）
                ocr_text = page_data.get("ocr_text", "")
                # if ocr_text:
                #     text_embedding = self.text_encoder.encode_text(ocr_text)
                #     # 融合图像和文本特征（简单拼接）
                #     combined_embedding = np.concatenate(
                #         [image_embedding, text_embedding])
                # else:
                #     combined_embedding = image_embedding

                # # 保存
                # embeddings.append(combined_embedding)
                # 保存
                embeddings.append(image_embedding)
                ids.append(page_data["page_id"])
                metadata_list.append({
                    "image_path": str(image_path),
                    "text_info": ocr_text[:200],  # 只保存前200字符
                    "edition_type": page_data.get("edition_type"),
                    "dynasty": page_data.get("dynasty"),
                    "institution": page_data.get("institution"),
                    "volume_number": page_data.get("volume_number"),
                    "page_number": page_data.get("page_number")
                })

            except Exception as e:
                logger.error(f"处理页面失败 {page_dir.name}: {e}")
                continue

        # 保存索引
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        embeddings_array = np.array(embeddings)
        np.save(output_dir / "embeddings.npy", embeddings_array)

        with open(output_dir / "ids.json", "w", encoding="utf-8") as f:
            json.dump(ids, f, ensure_ascii=False, indent=2)

        with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata_list, f, ensure_ascii=False, indent=2)

        logger.info(f"索引构建完成: {len(embeddings)} 条记录")
        logger.info(f"保存到: {output_dir}")

    def _load_page_data(self, page_dir: Path) -> Optional[Dict[str, Any]]:
        """加载页面数据.

        Args:
            page_dir: 页面目录

        Returns:
            页面数据字典
        """
        # 查找主JSON文件
        json_files = [f for f in page_dir.glob("*.json") if not f.name.endswith(
            "_raw.json") and f.name not in ["metadata.json", "extended_metadata.json"]]

        if not json_files:
            return None

        main_json = json_files[0]

        # 加载OCR数据
        with open(main_json, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)

        # 加载元数据
        metadata = {}
        metadata_path = page_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        # 提取信息
        text_lines = ocr_data.get("text_lines", [])
        ocr_text = "\n".join([line.get("text", "") for line in text_lines])
        # logger.info(f"加载OCR数据: {ocr_text} ")

        # 重定向image_path到真实的image文件
        # logger.info(f"json name: {main_json.name}")
        # 删除json后缀，重定向到overlay目录下jpg文件
        base_name = main_json.stem  # 去除.json后缀
        redirected_image_path = page_dir / \
            "overlay" / f"{base_name}_overlay.jpg"
        logger.info(f"重定向图像路径: {redirected_image_path} ")

        # 从目录名解析元数据
        import re
        import hashlib

        dir_name = page_dir.name

        page_data = {
            "page_id": f"page_{hashlib.md5(dir_name.encode()).hexdigest()[:12]}",
            "image_path": redirected_image_path,
            "ocr_text": ocr_text,
            "edition_type": None,
            "dynasty": None,
            "institution": None,
            "volume_number": None,
            "page_number": None
        }

        # 简单解析（实际应该更健壮）
        if "明" in dir_name:
            page_data["dynasty"] = "明"
        elif "清" in dir_name:
            page_data["dynasty"] = "清"
        elif "宋" in dir_name:
            page_data["dynasty"] = "宋"

        if "刻本" in dir_name:
            page_data["edition_type"] = "刻本"

        # 提取馆藏
        institution_match = re.search(r"([^#]+图书馆|[^#]+博物院)", dir_name)
        if institution_match:
            page_data["institution"] = institution_match.group(1).strip()

        return page_data


def main():
    """命令行入口."""
    import argparse

    parser = argparse.ArgumentParser(description="构建现代RAG索引")
    parser.add_argument("--data-dir", type=Path,
                        default=Path("outputs"), help="数据目录")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("rag/modern/indexes"), help="输出目录")
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 构建索引
    indexer = ModernIndexer()
    indexer.build_index(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
