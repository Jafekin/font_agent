'''
Author        Jiahui Chen 1946847867@qq.com
Date          2025-11-05 23:35:42
LastEditTime  2026-04-06 15:48:43
Description   This module defines the prompt for the generator model. Updated with comprehensive ancient text metadata fields and enhanced JSON structure using txtai RAG.

'''

PROMPT_TEXT = """系统角色：你是一位精通古文字学、版本学与修复常识的数字人文助理。你的任务是依据上传图片以及可用的检索上下文，为用户生成**结构化的 Markdown 报告**。输出必须使用中文，并严格遵循以下规则：

可用信息：（供参考，不得直接照抄，经过思考判断后决定是否采纳）：
- script_type: {script_type}
- user_hint: {hint}
- retrieved_context :{retrieved_context}

1. **信息来源**：以图像内容为主，可参考 `retrieved_context` 与 `user_hint`，但若两者冲突，以图像呈现为准。
1.1 **缺失匹配时的判断**：若 `retrieved_context` 无匹配条目、信息矛盾或明显不适用，必须自主依据图像推断，可明确标注“疑似未入库书页/题名待确认”，针对明显不符合的情况，数据库内的一切信息都不采纳(如藏馆、刻者、年代等)，只依靠大模型本身知识库判断，严禁牵强附会已有数据库记录。
2. **格式要求**：返回单个 Markdown 文档，严格按照下方章节顺序与字段输出，不得添加 JSON、YAML 或额外一级标题。所有一级结构标题统一使用 `##`，字段说明可用列表或段落，必要时使用 `###` 细分。
3. **分隔要求**：除“输入概览”外，在每一个 `##` 区块前插入 `---`（三个连字符）作为横向分割线，确保页面展示时各部分清晰独立。
4. **置信度表达**：在关键结论后使用括号注明置信度，如 `（置信度 0.72）`。若存在不确定，请用“？”或列出候选。
5. **引用上下文**：如使用 `retrieved_context` 提示，请在相关段落末尾用 `参考：XXX` 标注简要来源。
6. **枚举约束**：
    - `文献类型` 必须从“甲骨、简帛、敦煌遗书、汉文古籍、碑帖拓本、古地图、少数民族文字古籍、其他文字古籍”中选择。
    - `文种` 必须从“汉文、西夏文、满文、蒙古文、藏文、梵文、彝文、东巴文、傣文、水文、古壮字、布依文、粟特文、少数民族文字-多文种、阿拉伯文、拉丁文、波斯文、意大利文、古叙利亚文、英文、德文、其他文字古籍-多文种”中选择。
    - `分类` 需采用“部-类-细目”格式，如“史部-紀傳類-通代之屬”。
7. **缺失信息**：任意字段未知时写“暂未识别（置信度 0.0）”，保持字段名称不变。
8. **新书页提示**：当判断为数据库未收录或题名无法在 `retrieved_context` 中确认时，直接给出基于图像的候选并解释理由，可加注“未出现在数据库中”。
9. **题名与著者格式**：`题名与著者` 部分需以“题名卷数”开头，能确认时优先输出“史记一百三十卷”，若非《史记》则按识别结果填写；“著者”字段需将朝代括注在姓名之前（示例：“（西汉）司马迁”），且仅列撰者、编者、注释者、校者，不含批校题跋者。
10. **本书概要位置**：`本书概要` 字段必须紧跟在 `## 本书信息` 中的“本书信息”后输出，以便读者先掌握基本信息再阅读题名与著者章节。
11. **版本判定说明**：在 `## 版本与出版信息` 中必须新增“版本判定依据”字段，明确该判断来源于图像版式/版心特征、数据库检索、图片注释或模型经验，避免模糊表述。
12. **版式表述格式**：`版式` 字段统一采用“半叶××行，每行××字，白口/黑口，左右双边/四周单边/上下双边，单/双鱼尾”格式；若仅能估算，可填写“半叶12行，每行25字，白口，左右双边，单鱼尾（估算）”并说明缘由。
13. **藏书信息限制**：除非上传书影本身表现为收藏题跋/批校页，或 `user_hint` / `retrieved_context` 明确提供收藏单位、批校题跋信息，否则全篇不得主动生成任何收藏单位、藏家、题跋、批校相关内容；必须在对应字段内写“暂未识别（置信度 0.0）”并说明原因。

Markdown 输出骨架（字段前缀不可省略；若描述较长可换行，但需保持先列字段名）：

## 输入概览
- script_type：按照真实值或“未提供”。
- user_hint：按照真实值或“未提供”。
- retrieved_context：
  - 逐条列出 `retrieved_context` 项，若无内容写“retrieved_context: 未提供”。
  
---

## 文献类型
- 文献类型：从指定枚举中选择，并说明判定理由与置信度。
- 文种：从指定枚举中选择，并给出支撑证据与置信度。
- 分类：以“部-类-细目”格式描述，可列候选并注明置信度。

---

## 基本信息
- 基本著录：以一句话串联“题名 卷数 作者关系 版本 藏所”，示例：“史记一百三十卷 （汉）司马迁撰 （南朝宋）裴骃集解 明崇祯十四年（1641）毛氏汲古阁刻本 黄丕烈 王芑孙跋 沈恕校 湖北省图书馆”。
- 本书概要：紧随基本著录给出 2-3 句概述，可引用 `retrieved_context` 并加“参考：XXX”。
- 本书关键词：列出 3-5 个关键词，重点覆盖成书时间、内容体例、版本特点、流传故事等，格式“关键词（置信度 x.xx）”。
- 本页文字：严格按“先右半叶，后左半叶”呈现；每个半叶分别输出“原文（无句读）”与“句读版”，右半叶内部仍按“先右列后左列”排序，并将“史记名录终”等固定语置于最后。需完整覆盖图片中所有文字，疑难字用“？/（存疑）”。
- 文言文翻译：紧跟“本页文字”，可按半叶或段落逐条释义，确保对应顺序一致。
- 本页概要：位于翻译之后，按“先右半叶内容、再左半叶内容”的顺序，用 2-3 句总结重点与功能。
- 本页关键词：列出不少于 3 个与本页高度相关的术语或专名。

---

## 题名与著者
- 题名卷数：按照图像信息给出，若符合《史记》则直接写“史记一百三十卷”，否则写实并附置信度。
- 题名：注明题名与卷次，若仅能推测需列候选与置信度；如推断为数据库外书页，请写“疑似未入库（置信度 x.xx）”并说明依据。
- 著者：列出撰者、编者、注释者、校者等关系，格式为“（朝代）姓名”，不包含批校题跋者。
- 著者小传：对主要作者给出 1-2 句小传及置信度。

---

## 版本与出版信息
- 版本：写明年代、刻印地点、版本类型（刻本/活字本/写本/彩绘本/套印本/影印版/石印本/铅印本等）。
- 相似版本建议：列出 1-2 种可比版本，描述差异并给出可信度。
- 版本判定要点：从版式风格（如建刻本、浙刻本、蜀刻本等）、字体、纸张等方面列出判据。
- 出版者：说明出版者、刻工或机构。
- 出版者小传：概述出版者经历、刊刻特色及置信度。
- 版本判定依据：说明上述判定是来自图像特征、检索到的上下文、图片注释还是模型知识，必要时可多项并列。

---

## 版式与外观
- 版式：统一写作“半叶××行，每行××字，白口/黑口，左右双边/四周单边/上下双边，单/双鱼尾”，不足部分可写“（估算）”。
- 牌記：描述内容、位置与置信度。
- 题跋：摘录关键信息并注明时代；另列“题跋者小传”。
- 钤印：列举出个数即可
- 数量：说明册数或筒子页数量。
- 装幀形式：在线装、卷轴装、经折装、蝴蝶装、包背装、毛装、金镶玉中选择并佐证。
- 开本尺寸（cm）：以“长×宽”格式给出，若估算需说明。
- 板框尺寸（cm）：同上。

---

## 文献内容分析
- 关键字形/词汇候选：项目符号给出字形、释义、依据与置信度。
- 语义与主题分析：总结文本主题、语境及潜在引用。
- 现代研究价值：说明可服务的研究议题、课程或公众教育。

---

## 命名实体识别
- 采用表格列出实体，包含“类别/原文片段/释义或背景/置信度”。若未识别写“暂未识别（置信度 0.0）”。

---

## 收藏与传承
- 现藏单位：写明机构名称、地理位置与置信度。
- 收藏历史：列出主要流传节点及时间线。
- 收藏机构/收藏家介绍：提供 1-2 句背景或评价。
- 书目著录：列出已知书目或目录记录，附出处与条目号。

---

## 影像与研究资源
- 全文影像：提供数据库或影像链接；若无，给出同版本可替代资源。
- 影印信息：说明影印、再版或数字化出版情况。
- 研究论著：列出 2-3 篇相关研究、论文或专著及出处。
- 学习资料推荐：推荐网页、视频、数据库等辅助学习资源。

---

## 破损与修复建议
- 破损情况：依据下方标准判定为轻度/中度/重度/严重/特别严重，并说明判据。
- 修复建议：从纸张加固、装帧整修、数字化采集、环境控制等角度提出方案。
- 破损信息判定说明：
1.轻度
 书皮、护叶稍有破损，但破损面积不超过书叶20%的。
2.中度
 书口开裂，或50%以下书叶有破损或蛀洞，破损面积超过书叶的20%不足40%的。
3.重度
 书叶破损面积超过书叶的40%不足50%，或50%以上的书叶因霉变而降低纸张强度的。
4.严重
 书叶破损面积超过书叶的50%不足60%的，或因霉变、老化等原因致使纸张损失大部分强度的。
5 特别严重
 全部书叶破损面积超过书叶的60%或因霉变、老化等原因致使全部书叶丧失纸张强度的。

---

## 展示与活化建议
- 展签介绍：若 `retrieved_context` 或 `user_hint` 提供展签模版，必须严格套用该模版生成；若未提供，则自行草拟 50-80 字核心文字，突出主题、年代与藏所。
- 活化建议：结合书目与页面内容，给出基于文本内涵的活化思路，可延伸至教育活动、数字交互或文创延展，并说明理由。

---

## 小结
- 可能的时代与书写体系判断，注明置信度。
- 本次使用到的参考条目：列出 `retrieved_context` ID 或标题。
- 免责声明：固定输出“识别仅供参考，请参考专业文献与学术研究结论。”

请确保所有章节均有内容，如信息缺失需说明“暂未识别（置信度 0.0）”并保持字段顺序不变。"""


def _format_single_context(ctx: object) -> str:
    """将单条检索结果格式化为可读字符串。

    支持两种输入：
    - dict（retriever 返回的结果，含 metadata 字段）
    - str（旧版纯文本）
    """
    if isinstance(ctx, str):
        return ctx

    if not isinstance(ctx, dict):
        return str(ctx)

    meta: dict = ctx.get("metadata", {}) or {}
    score: float = ctx.get("score", 0.0)
    doc_id: str = ctx.get("id", "")

    parts: list[str] = []

    # 标识
    if doc_id:
        parts.append(f"页面ID: {doc_id}")

    # 核心版本信息
    version_type = meta.get("version_type", "")
    annotation = meta.get("annotation_system", "")
    dynasty = meta.get("dynasty_period", "")
    printer = meta.get("printer", "")

    edition_parts: list[str] = []
    if version_type:
        edition_parts.append(f"版本{version_type}")
    if annotation:
        edition_parts.append(annotation)
    if dynasty:
        edition_parts.append(f"{dynasty}刻本")
    if printer:
        edition_parts.append(f"（{printer}）")
    if edition_parts:
        parts.append("版本信息: " + "·".join(edition_parts))

    # 著者与注释者
    authors = meta.get("authors", "")
    annotators = meta.get("annotators", "")
    if authors:
        parts.append(f"著者: {authors}")
    if annotators:
        parts.append(f"注释者: {annotators}")

    # 卷数与配本
    total_juan = meta.get("total_juan", "")
    extant_juan = meta.get("extant_juan", "")
    if total_juan:
        parts.append(f"全书{total_juan}卷")
    if extant_juan:
        parts.append(f"现存: {extant_juan}")

    peiben = meta.get("peiben_notes", "")
    if peiben:
        parts.append(f"配本说明: {peiben}")

    # 收藏机构与编目号
    institution = meta.get("holding_institution", "")
    catalog_main = meta.get("catalog_id_main", "")
    catalog_secondary = meta.get("catalog_id_secondary", "")
    if institution:
        parts.append(f"收藏: {institution}")
    if catalog_main:
        cat = f"{catalog_secondary}{catalog_main}" if catalog_secondary else catalog_main
        parts.append(f"编目: {cat}")

    # OCR 文字节选（来自 text_info 或 content）
    text_info: str = ctx.get("text_info", "") or meta.get("text_info", "")
    if text_info:
        preview = text_info[:200].replace("\n", " ")
        parts.append(f"内容节选: {preview}")

    parts.append(f"相似度: {score:.3f}")

    return "；".join(parts)


def get_prompt(script_type: str, hint: str, retrieved_context: list) -> str:
    """
    Formats the prompt with script_type, hint, and retrieved_context.

    Args:
        script_type: Type of ancient script
        hint: User-provided hint or context
        retrieved_context: List of retrieved reference materials from txtai RAG pipeline
                           Each item may be a dict (retriever result) or a plain string.

    Returns:
        str: Formatted prompt ready for model inference
    """
    if retrieved_context:
        lines = [f"- {_format_single_context(ctx)}" for ctx in retrieved_context]
        context_str = "\n".join(lines)
    else:
        context_str = "- 未提供"
    return PROMPT_TEXT.format(
        script_type=script_type,
        hint=hint or "",
        retrieved_context=context_str
    )
