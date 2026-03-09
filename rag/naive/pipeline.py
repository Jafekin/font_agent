"""RAG (Retrieval-Augmented Generation) 管道和统一的 LLM 接入。"""
from typing import Optional, Dict, Any, List
import base64
import io
import os
import logging
import traceback

from rag.embeddings import get_image_embedding, get_text_embedding
from rag.retriever import TxtaiRetriever
from rag.prompt import get_prompt
from PIL import Image

try:
    from django.conf import settings as django_settings
    from django.core.exceptions import ImproperlyConfigured
except Exception:  # pragma: no cover - 非 Django 环境降级
    django_settings = None
    ImproperlyConfigured = None

# 配置日志
logger = logging.getLogger(__name__)


_OPENAI_CLIENT = None


def _get_setting_or_env(setting_name: str, env_key: str) -> Optional[str]:
    """Return Django setting if configured, otherwise fallback to env."""
    env_value = os.getenv(env_key)
    if env_value:
        return env_value

    if django_settings is not None and os.getenv("DJANGO_SETTINGS_MODULE"):
        try:
            if getattr(django_settings, "configured", False):
                value = getattr(django_settings, setting_name, None)
                if value:
                    return value
        except ImproperlyConfigured:  # pragma: no cover - Django尚未初始化
            logger.debug(
                "Django settings not configured; using environment variables")
        except Exception:  # pragma: no cover - 其他异常
            logger.debug(
                "Failed to read Django setting; using environment variables", exc_info=True)
    return env_value


def get_openai_client():
    """Lazy initialization for OpenAI client reused across app and RAG."""
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is not None:
        return _OPENAI_CLIENT

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - 依赖缺失
        raise ImportError(
            "OpenAI library is not installed. Please install it with: pip install openai"
        ) from exc

    api_key = _get_setting_or_env('OPENAI_API_KEY', 'OPENAI_API_KEY')
    base_url = _get_setting_or_env('OPENAI_BASE_URL', 'OPENAI_BASE_URL')
    client_kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    _OPENAI_CLIENT = OpenAI(**client_kwargs)
    return _OPENAI_CLIENT


def _build_default_prompt(script_type: str, hint: str) -> str:
    """Default detailed prompt when RAG prompt is not provided."""
    hint_text = hint.strip() if hint else '（未提供）'
    return (
        "你是一位古籍文献识别与编目助手。仅基于上传图片进行判断，不要引入图片之外的信息。"
        f"若用户提供提示（时代/文本片段/出处等），可参考但仍以图像为主。目标类型：{script_type}。"
        "请用中文 Markdown 分节输出：\n\n"
        "# 文献类型\n"
        "请从以下类型中选择最匹配的,只输出最终结果，不输出思考过程：甲骨、简帛、敦煌遗书、汉文古籍、碑帖拓本、古地图、少数民族文字古籍、其他文字古籍\n\n"
        "# 文种\n"
        "请从以下文种中选择：汉文、西夏文、满文、蒙古文、藏文、梵文、彝文、东巴文、傣文、水文、古壮字、布依文、粟特文、少数民族文字-多文种、阿拉伯文、拉丁文、波斯文、意大利文、古叙利亚文、英文、德文、其他文字古籍-多文种\n\n"
        "# 分类\n"
        "按四部分类法给出分类，格式示例：史部-紀傳類-通代之屬\n\n"
        "# 题名\n"
        "识别并给出古籍的题名及卷数，格式示例：史记一百三十卷\n\n"
        "# 本书信息\n"
        "综合给出本书完整信息，格式示例：史记一百三十卷　（汉）司马迁撰　（南朝宋）裴骃集解　（唐）司马贞索隐　（唐）张守节正义　明嘉靖四至六年（1525-1527）王延喆刻本　四川省图书馆\n\n"
        "# 著者\n"
        "识别著者信息，格式示例：（汉）司马迁撰　（南朝宋）裴骃集解　（唐）司马贞索隐　（唐）张守节正义\n\n"
        "# 著者小传\n"
        "简要介绍主要著者的生平和贡献\n\n"
        "# 版本\n"
        "识别版本信息，格式示例：明嘉靖四至六年（1525-1527）王延喆刻本\n\n"
        "# 版本判定要点及依据\n"
        "- 版本类型：刻本、活字本、写本、彩绘本、套印本、影印版、石印本、铅印本等\n"
        "- 版式风格：建刻本、浙刻本、蜀刻本等\n"
        "- 特征分析：字体、刻工、纸张、墨色、行款等特征\n"
        "- 可信度说明：给出版本判定的可信度及理由\n\n"
        "# 相似版本建议\n"
        "列出与本版本相似的其他版本，并说明相似之处\n\n"
        "# 出版者\n"
        "识别并说明出版者信息\n\n"
        "# 出版者小传\n"
        "简要介绍出版者的背景\n\n"
        "# 版式\n"
        "格式示例：××行行××字小字双行××字白口/黑口，左右双边/四周单边/上下双边\n\n"
        "# 牌記\n"
        "识别并转录书中的牌记内容\n\n"
        "# 题跋\n"
        "识别并转录书中的题跋内容\n\n"
        "# 题跋者小传\n"
        "简要介绍题跋者背景\n\n"
        "# 钤印\n"
        "- 印文释文\n"
        "- 印主信息\n"
        "- 印主小传\n"
        "- 曾见某书\n\n"
        "# 數量\n"
        "格式示例：××册××筒子页\n\n"
        "# 裝幀形式\n"
        "请从以下类型中选择：线装、卷轴装、经折装、蝴蝶装、包背装、毛装、金镶玉\n\n"
        "# 開本尺寸（cm）\n"
        "格式示例：22×12\n\n"
        "# 板框尺寸（cm）\n"
        "格式示例：17.6×12.5\n\n"
        "# 现藏单位\n"
        "识别或推测现藏单位\n\n"
        "# 收藏历史\n"
        "- 以往收藏该部古籍的收藏机构/收藏家\n"
        "- 收藏机构/收藏家介绍\n\n"
        "# 本页释文\n"
        "给出本页的详细释文，不确定处用□或？标注\n\n"
        "# 本页概要\n"
        "简要概括本页内容要点\n\n"
        "# 本页文言文翻译\n"
        "将本页内容翻译成现代汉语\n\n"
        "# 本页关键词\n"
        "列出本页涉及的关键词汇\n\n"
        "# 本书关键词\n"
        "列出本书的主题关键词\n\n"
        "# 本书概要\n"
        "简要介绍本书的主要内容和价值\n\n"
        "# 书目著录\n"
        "列出本书在各种书目中的著录情况，如《中国古籍善本书目》等\n\n"
        "# 全文影像\n"
        "- 提供相关数据库链接（如有）\n"
        "- 如无此版本，可提供同版本的全文影像链接\n\n"
        "# 影印信息\n"
        "列出本书的影印出版信息\n\n"
        "# 研究论著\n"
        "列出与本书相关的主要研究论著\n\n"
        "# 破损情况\n"
        "根据以下标准判定：\n"
        "- 轻度破损：书皮、护叶稍有破损，但破损面积不超过书叶20%\n"
        "- 中度破损：书口开裂，或50%以下书叶有破损或蛀洞，破损面积超过书叶的20%不足40%\n"
        "- 重度破损：书叶破损面积超过书叶的40%不足50%，或50%以上的书叶因霉变而降低纸张强度\n"
        "- 严重破损：书叶破损面积超过书叶的50%不足60%，或因霉变、老化等原因致使纸张损失大部分强度\n"
        "- 特别严重：全部书叶破损面积超过书叶的60%或因霉变、老化等原因致使全部书叶丧失纸张强度\n\n"
        "# 修复建议\n"
        "根据破损情况提出具体的修复建议\n\n"
        "# 展签介绍\n"
        "为本书撰写展览说明文字\n\n"
        "# 活化建议\n"
        "提出古籍活化利用的建议\n\n"
        "# 学习资料推荐\n"
        "推荐相关的学习资料，包括网页、视频、数据库等\n\n"
        f"# 用户提示\n{hint_text}\n\n"
        "# 免责声明\n"
        "识别仅供参考，请参考专业文献与学术研究结论。\n"
    )


def analyze_with_llm(
    image: Image.Image | bytes | str,
    script_type: str = "甲骨文",
    hint: str = "",
    prompt_text: Optional[str] = None,
    model: str = "ernie-4.5-turbo-vl"
) -> str:
    """Call the LLM with provided image and prompt."""
    if prompt_text is None:
        prompt_text = _build_default_prompt(script_type, hint)

    if isinstance(image, Image.Image):
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    elif isinstance(image, (bytes, bytearray)):
        image_base64 = base64.b64encode(image).decode('utf-8')
    else:
        image_base64 = str(image)

    client = get_openai_client()
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        stream=False,
    )

    return completion.choices[0].message.content or "无法识别古文字内容"


class RAGPipeline:
    """
    RAG管道，协调检索 + 提示词增强 + 下游分析

    工作流程：
    1. 用户上传图片
    2. 从知识库中检索相似图片及其对应的文字信息
    3. 将检索到的文字信息构建增强提示词
    4. 调用LLM生成分析结果
    """

    def __init__(self, index_path: str | None = None, db_path: Optional[str] = None):
        """
        初始化RAG管道

        Args:
            index_path: numpy 索引路径（包含 embeddings.npy 等文件）
            db_path: 数据库路径（可选，用于未来扩展）
        """
        self.retriever = TxtaiRetriever(index_path)
        self.db_path = db_path

    # ------------------------------------------------------------------
    # 核心执行
    # ------------------------------------------------------------------
    def run(
        self,
        image_path: str,
        script_type: str,
        hint: Optional[str] = None,
        k: int = 3,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行完整的RAG流程

        Args:
            image_path: 用户上传的图片路径
            script_type: 文字类型（如"汉文古籍"）
            hint: 用户提示（可选）
            k: 检索top-k个相似图片
            metadata_filters: 元数据过滤条件（可选）

        Returns:
            包含分析结果和检索信息的字典：
            {
                "success": bool,
                "analysis": dict,  # LLM分析结果
                "retrieved_references": list,  # 检索到的图片ID列表
                "retrieved_text_info": list,  # 检索到的文字信息列表
                "num_references": int,
                "retrieval_scores": list,
                "citations": list,
                "pipeline_mode": str
            }
        """
        try:
            # 步骤1: 通过图片路径直接搜索相似图片
            logger.info(f"开始检索相似图片: {image_path}, k={k}")
            retrieved_results = self.retriever.search_by_image(
                image_path,
                k=k,
                filters=metadata_filters
            )
            logger.info(f"检索完成，找到 {len(retrieved_results)} 个结果")

            # 步骤2: 提取检索到的文字信息
            retrieved_context: List[str] = []
            retrieved_text_info: List[str] = []
            used_references: List[str] = []

            for result in retrieved_results:
                # 获取图片对应的文字信息
                text_info = result.get("text_info", "")
                content = result.get("content", "")

                # 优先使用text_info，如果没有则使用content
                if text_info and text_info.strip():
                    retrieved_text_info.append(text_info)
                    retrieved_context.append(text_info)
                elif content and not content.endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    # content不是图片路径，可能是文字
                    retrieved_context.append(content)

                used_references.append(result.get("id", "unknown"))

            logger.info(f"提取到 {len(retrieved_context)} 条文字信息")

            # 步骤3: 构建增强提示词
            # 将检索到的文字信息作为上下文传递给LLM
            prompt = get_prompt(script_type, hint or "", retrieved_context)
            logger.info(f"提示词长度: {len(prompt)} 字符")

            # 步骤4: 调用LLM进行分析
            logger.info("开始调用LLM进行分析...")
            try:
                image_obj = Image.open(image_path)
                logger.info(f"成功加载图片: {image_path}")
            except Exception as img_error:
                logger.error(f"加载图片失败: {img_error}")
                raise

            analysis_result = analyze_with_llm(
                image_obj, script_type, hint or "", prompt)
            logger.info("LLM分析完成")

            # 步骤5: 生成引用（可选）
            citations = []
            if isinstance(analysis_result, dict):
                # 尝试从分析结果中提取文本用于引用
                answer_text = (
                    analysis_result.get("page_content", {}).get("page_summary")
                    or analysis_result.get("title", {}).get("title_text")
                    or str(analysis_result)
                )
                citations = self.retriever.cite(answer_text, k=min(3, k))

            return {
                "success": True,
                "analysis": analysis_result,
                "retrieved_references": used_references,
                "retrieved_text_info": retrieved_text_info,  # 新增：检索到的文字信息
                "num_references": len(retrieved_results),
                "retrieval_scores": [r.get("score", 0) for r in retrieved_results],
                "citations": citations,
                "pipeline_mode": "fake" if not self.retriever.is_ready() else "real"
            }
        except Exception as e:
            logger.error(f"RAG pipeline执行失败: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "analysis": None,
                "retrieved_references": [],
                "retrieved_text_info": []
            }

    def search_similar(
        self,
        query_image_path: Optional[str] = None,
        query_text: Optional[str] = None,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        相似度搜索（仅检索，不调用LLM）

        Args:
            query_image_path: 查询图片路径
            query_text: 查询文本
            k: 返回top-k结果

        Returns:
            搜索结果列表，每个结果包含：
            - id: 文档ID
            - score: 相似度分数
            - image_path: 图片路径
            - text_info: 对应的文字信息
            - metadata: 元数据
        """
        if query_image_path:
            return self.retriever.search_by_image(query_image_path, k=k)
        if query_text:
            return self.retriever.search(query_text, k=k)
        raise ValueError("必须提供query_image_path或query_text之一")

    def batch_analyze(
        self,
        image_paths: List[str],
        script_type: str,
        hints: Optional[List[str]] = None,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        批量RAG分析多个图片

        Args:
            image_paths: 图片路径列表
            script_type: 文字类型
            hints: 提示列表（可选，长度应与image_paths相同）
            k: 每个图片检索top-k个相似图片

        Returns:
            每个图片的分析结果列表
        """
        if not image_paths:
            raise ValueError("image_paths必须非空")
        hints = hints or [None] * len(image_paths)
        results: List[Dict[str, Any]] = []
        for image_path, hint in zip(image_paths, hints):
            results.append(self.run(image_path, script_type, hint, k))
        return results

    def cite(self, answer_text: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        公共引用辅助方法（供外部重用）

        Args:
            answer_text: 答案文本
            k: 返回top-k引用

        Returns:
            引用候选列表
        """
        return self.retriever.cite(answer_text, k=k)

    def get_text_info_for_image(
        self,
        image_path: str,
        k: int = 1
    ) -> List[str]:
        """
        获取指定图片对应的文字信息

        Args:
            image_path: 图片路径
            k: 返回top-k结果（通常只需要最相似的1个）

        Returns:
            文字信息列表
        """
        results = self.retriever.search_by_image(image_path, k=k)
        text_info_list = []
        for result in results:
            text_info = result.get("text_info", "")
            if text_info and text_info.strip():
                text_info_list.append(text_info)
        return text_info_list
