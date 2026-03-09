"""数据加载器 - 从 outputs/ 目录加载 OCR 结果和元数据."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OutputsDataLoader:
    """从 outputs/ 目录加载结构化数据."""

    def __init__(self, outputs_dir: Path):
        """初始化数据加载器.

        Args:
            outputs_dir: outputs 目录路径
        """
        self.outputs_dir = Path(outputs_dir)
        if not self.outputs_dir.exists():
            raise ValueError(f"outputs 目录不存在: {outputs_dir}")

    def load_all_pages(self) -> List[Dict[str, Any]]:
        """加载所有页面数据.

        Returns:
            页面数据列表，每个包含：
            - page_id: 页面唯一标识
            - image_path: 原始图片路径
            - ocr_text: OCR 识别文本
            - ocr_confidence: 平均置信度
            - text_lines: 文本行列表
            - metadata: 扩展元数据（版本、卷次、馆藏等）
            - statistics: 统计信息
        """
        logger.info(f"开始从 {self.outputs_dir} 加载数据")

        pages = []
        page_dirs = [d for d in self.outputs_dir.iterdir() if d.is_dir()]

        logger.info(f"找到 {len(page_dirs)} 个页面目录")

        for page_dir in page_dirs:
            try:
                page_data = self._load_page_data(page_dir)
                if page_data:
                    pages.append(page_data)
            except Exception as e:
                logger.error(f"加载页面 {page_dir.name} 失败: {e}")
                continue

        logger.info(f"成功加载 {len(pages)} 个页面")
        return pages

    def _load_page_data(self, page_dir: Path) -> Optional[Dict[str, Any]]:
        """加载单个页面的数据.

        Args:
            page_dir: 页面目录路径

        Returns:
            页面数据字典
        """
        # 查找 JSON 文件
        json_files = list(page_dir.glob("*.json"))
        if not json_files:
            logger.warning(f"页面目录 {page_dir.name} 中没有 JSON 文件")
            return None

        # 优先加载主 JSON 文件（不是 metadata.json 或 extended_metadata.json）
        main_json = None
        metadata_json = None
        extended_metadata_json = None

        for json_file in json_files:
            if json_file.name == "metadata.json":
                metadata_json = json_file
            elif json_file.name == "extended_metadata.json":
                extended_metadata_json = json_file
            elif not json_file.name.endswith("_raw.json"):
                main_json = json_file

        if not main_json:
            logger.warning(f"页面目录 {page_dir.name} 中没有主 JSON 文件")
            return None

        # 加载主 JSON
        with open(main_json, "r", encoding="utf-8") as f:
            ocr_data = json.load(f)

        # 加载 metadata.json
        metadata = {}
        if metadata_json and metadata_json.exists():
            with open(metadata_json, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        # 加载 extended_metadata.json
        extended_metadata = {}
        if extended_metadata_json and extended_metadata_json.exists():
            with open(extended_metadata_json, "r", encoding="utf-8") as f:
                extended_metadata = json.load(f)

        # 提取页面信息
        page_id = self._generate_page_id(page_dir.name)
        image_path = metadata.get("source_image", "")
        text_lines = ocr_data.get("text_lines", [])
        ocr_text = self._extract_full_text(text_lines)
        ocr_confidence = self._calculate_average_confidence(text_lines)

        # 解析目录名获取版本信息
        parsed_info = self._parse_directory_name(page_dir.name)

        # 合并元数据
        page_data = {
            "page_id": page_id,
            "image_path": image_path,
            "ocr_text": ocr_text,
            "ocr_confidence": ocr_confidence,
            "text_lines": text_lines,
            "text_direction": "vertical" if metadata.get("statistics", {}).get("is_vertical", True) else "horizontal",
            "line_count": len(text_lines),
            "width": metadata.get("statistics", {}).get("image_size", {}).get("width"),
            "height": metadata.get("statistics", {}).get("image_size", {}).get("height"),
            "timestamp": metadata.get("timestamp"),
            # 版本信息
            "version_type": parsed_info.get("version_type"),
            "edition_info": parsed_info.get("edition_info"),
            "edition_type": parsed_info.get("edition_type"),
            "edition_name": parsed_info.get("edition_name"),
            "publisher": parsed_info.get("publisher"),
            "publish_year": parsed_info.get("publish_year"),
            # 文献信息
            "document_title": parsed_info.get("document_title", "史记"),
            "author": parsed_info.get("author", "司马迁"),
            "dynasty": parsed_info.get("dynasty"),
            "volume_number": parsed_info.get("volume_number"),
            "volume_title": parsed_info.get("volume_title"),
            "page_number": parsed_info.get("page_number"),
            # 馆藏信息
            "institution": parsed_info.get("institution"),
            "catalog_number": parsed_info.get("catalog_number"),
            "completeness": parsed_info.get("completeness"),
            # 扩展元数据
            "extended_metadata": extended_metadata,
        }

        return page_data

    def _generate_page_id(self, dir_name: str) -> str:
        """生成页面 ID.

        Args:
            dir_name: 目录名

        Returns:
            页面 ID
        """
        # 使用目录名的哈希作为 ID
        import hashlib
        return f"page_{hashlib.md5(dir_name.encode()).hexdigest()[:12]}"

    def _extract_full_text(self, text_lines: List[Dict[str, Any]]) -> str:
        """提取完整文本.

        Args:
            text_lines: 文本行列表

        Returns:
            完整文本
        """
        return "\n".join([line.get("text", "") for line in text_lines])

    def _calculate_average_confidence(self, text_lines: List[Dict[str, Any]]) -> float:
        """计算平均置信度.

        Args:
            text_lines: 文本行列表

        Returns:
            平均置信度
        """
        if not text_lines:
            return 0.0

        total_confidence = 0.0
        word_count = 0

        for line in text_lines:
            words = line.get("words", [])
            for word in words:
                confidence = word.get("confidence", 0.0)
                total_confidence += confidence
                word_count += 1

        return total_confidence / word_count if word_count > 0 else 0.0

    def _parse_directory_name(self, dir_name: str) -> Dict[str, Any]:
        """解析目录名提取版本信息.

        目录名格式示例：
        名录 史记2025-11-6_B史记 集解、索隐合刻本 4明正德十三年（1518）邵宗周刻本_
        【4】10160 （四）00096 史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解
        （唐）司马贞索隐 明正德十三年（1518）邵宗周刻本 欧阳辅跋 江西省图书馆#存一百二十六卷_
        史記·卷四十p1a

        Args:
            dir_name: 目录名

        Returns:
            解析后的信息字典
        """
        info = {}

        # 提取版本类型 (A/B/C/D/E)
        version_match = re.search(r"_([A-E])史记", dir_name)
        if version_match:
            info["version_type"] = version_match.group(1)

        # 提取版本信息（第一个下划线后到第二个下划线之间）
        parts = dir_name.split("_")
        if len(parts) >= 2:
            edition_part = parts[1]
            info["edition_info"] = edition_part

            # 提取版本类型（集解本、集解索隐合刻本等）
            if "集解本" in edition_part:
                info["edition_type"] = "集解本"
            elif "集解、索隐合刻本" in edition_part:
                info["edition_type"] = "集解、索隐合刻本"
            elif "集解、索隐、正义三家注本" in edition_part:
                info["edition_type"] = "集解、索隐、正义三家注本"

            # 提取朝代和年份
            dynasty_match = re.search(r"(宋|明|清|元|北宋|南宋)", edition_part)
            if dynasty_match:
                info["dynasty"] = dynasty_match.group(1)

            year_match = re.search(r"([明清宋元][^年]*年[^）]*）)", edition_part)
            if year_match:
                info["publish_year"] = year_match.group(1)

            # 提取出版者
            publisher_match = re.search(r"（\d+）([^刻本]+)刻本", edition_part)
            if publisher_match:
                info["publisher"] = publisher_match.group(1)

        # 提取馆藏信息
        if len(parts) >= 3:
            catalog_part = parts[2]

            # 提取馆藏机构
            institution_match = re.search(r"([^#]+图书馆|[^#]+博物院)", catalog_part)
            if institution_match:
                info["institution"] = institution_match.group(1).strip()

            # 提取目录号
            catalog_match = re.search(r"【(\d+)】(\d+)", catalog_part)
            if catalog_match:
                info["catalog_number"] = f"{catalog_match.group(1)}-{catalog_match.group(2)}"

            # 提取完整性信息
            completeness_match = re.search(r"#存(.+?)(?:_|$)", catalog_part)
            if completeness_match:
                info["completeness"] = completeness_match.group(1)

        # 提取卷次和页码信息
        if len(parts) >= 4:
            page_part = parts[-1]

            # 提取卷号
            volume_match = re.search(r"卷[之]?([一二三四五六七八九十百]+|[\d]+)", page_part)
            if volume_match:
                volume_str = volume_match.group(1)
                info["volume_title"] = f"卷{volume_str}"
                # 尝试转换为数字
                try:
                    info["volume_number"] = self._chinese_to_number(volume_str)
                except:
                    info["volume_number"] = 1

            # 提取页码
            page_match = re.search(r"p(\d+)([ab])?", page_part)
            if page_match:
                page_num = int(page_match.group(1))
                page_side = page_match.group(2) or ""
                info["page_number"] = page_num
                info["page_side"] = page_side

        # 设置默认值
        info.setdefault("document_title", "史记")
        info.setdefault("author", "司马迁")
        info.setdefault("edition_name", info.get("edition_info", "未知版本"))

        return info

    def _chinese_to_number(self, chinese_num: str) -> int:
        """将中文数字转换为阿拉伯数字.

        Args:
            chinese_num: 中文数字字符串

        Returns:
            阿拉伯数字
        """
        # 如果已经是数字，直接返回
        if chinese_num.isdigit():
            return int(chinese_num)

        chinese_map = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            "百": 100, "千": 1000
        }

        result = 0
        temp = 0
        unit = 1

        for char in reversed(chinese_num):
            if char in ["十", "百", "千"]:
                unit = chinese_map[char]
                if temp == 0:
                    temp = 1
            else:
                temp = chinese_map.get(char, 0)

            result += temp * unit
            temp = 0
            if char not in ["十", "百", "千"]:
                unit = 1

        return result if result > 0 else 1

    def extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取实体（人名、地名等）.

        Args:
            text: OCR 文本

        Returns:
            实体列表
        """
        entities = []

        # 简单的规则提取（实际应用中可以使用 NER 模型）
        # 提取常见人名
        person_patterns = [
            r"司马[迁贞]",
            r"裴骃",
            r"张守节",
            r"黄帝",
            r"孔[子安國]",
            r"[王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段漕钱汤尹黎易常武乔贺赖龚文][一-龥]{1,2}",
        ]

        for pattern in person_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity_text = match.group()
                entities.append({
                    "entity_text": entity_text,
                    "entity_type": "PERSON",
                    "position": match.span(),
                })

        # 提取地名
        place_patterns = [
            r"[京洛长安咸阳临淄邯郸大梁成都][都城]",
            r"[河山][东西南北]",
            r"[一-龥]{2,4}[郡县国]",
        ]

        for pattern in place_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity_text = match.group()
                entities.append({
                    "entity_text": entity_text,
                    "entity_type": "PLACE",
                    "position": match.span(),
                })

        return entities

    def get_statistics(self) -> Dict[str, Any]:
        """获取数据集统计信息.

        Returns:
            统计信息字典
        """
        pages = self.load_all_pages()

        stats = {
            "total_pages": len(pages),
            "version_distribution": {},
            "edition_distribution": {},
            "institution_distribution": {},
            "average_confidence": 0.0,
            "total_text_lines": 0,
        }

        total_confidence = 0.0

        for page in pages:
            # 版本分布
            version_type = page.get("version_type") or "未知"
            stats["version_distribution"][version_type] = stats["version_distribution"].get(version_type, 0) + 1

            # 版本类型分布
            edition_type = page.get("edition_type") or "未知"
            stats["edition_distribution"][edition_type] = stats["edition_distribution"].get(edition_type, 0) + 1

            # 馆藏分布
            institution = page.get("institution") or "未知"
            stats["institution_distribution"][institution] = stats["institution_distribution"].get(institution, 0) + 1

            # 置信度
            total_confidence += page.get("ocr_confidence", 0.0)

            # 文本行数
            stats["total_text_lines"] += page.get("line_count", 0)

        stats["average_confidence"] = total_confidence / len(pages) if pages else 0.0

        return stats
