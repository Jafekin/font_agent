"""RAG 评估指标库（纯 Python，无外部 NLP 依赖）。

检索指标：
  - Precision@K, Recall@K, F1@K
  - MRR（Mean Reciprocal Rank）
  - NDCG@K（Normalized Discounted Cumulative Gain）
  - Hit Rate@K

生成指标：
  - BLEU-1/2/3/4（字符级 n-gram，适配中文）
  - ROUGE-1/2/L（字符级）
  - 精确匹配（Exact Match）
  - 字符级 F1（Character F1）
  - 答案相关性（Answer Relevance，基于关键词覆盖）
  - 忠实度（Faithfulness，生成内容与检索上下文的覆盖率）
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# 文本预处理
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """中文字符级分词（每个汉字/标点作为一个 token）。"""
    text = re.sub(r"\s+", "", text)
    return list(text)


def _ngrams(tokens: List[str], n: int) -> Counter:
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


# ---------------------------------------------------------------------------
# 检索指标
# ---------------------------------------------------------------------------

@dataclass
class RetrievalMetrics:
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    mrr: float = 0.0
    ndcg: float = 0.0
    hit_rate: float = 0.0


def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Precision@K：前 K 个结果中相关文档的比例。"""
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return sum(1 for r in top_k if r in relevant) / k


def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Recall@K：前 K 个结果覆盖了多少相关文档。"""
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    return sum(1 for r in top_k if r in relevant) / len(relevant)


def f1_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    p = precision_at_k(retrieved, relevant, k)
    r = recall_at_k(retrieved, relevant, k)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def reciprocal_rank(retrieved: List[str], relevant: Set[str]) -> float:
    """MRR 单条：第一个相关结果的倒数排名。"""
    for i, r in enumerate(retrieved, 1):
        if r in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """NDCG@K（二元相关性）。"""
    top_k = retrieved[:k]
    dcg = sum(
        1.0 / math.log2(i + 2)
        for i, r in enumerate(top_k)
        if r in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def hit_rate_at_k(retrieved: List[str], relevant: Set[str], k: int) -> bool:
    """Hit Rate@K：前 K 个结果中是否至少有一个相关文档。"""
    return any(r in relevant for r in retrieved[:k])


def compute_retrieval_metrics(
    retrieved: List[str],
    relevant: Set[str],
    k: int,
) -> RetrievalMetrics:
    """计算单条查询的全部检索指标。"""
    return RetrievalMetrics(
        precision=precision_at_k(retrieved, relevant, k),
        recall=recall_at_k(retrieved, relevant, k),
        f1=f1_at_k(retrieved, relevant, k),
        mrr=reciprocal_rank(retrieved, relevant),
        ndcg=ndcg_at_k(retrieved, relevant, k),
        hit_rate=float(hit_rate_at_k(retrieved, relevant, k)),
    )


def aggregate_retrieval_metrics(metrics: List[RetrievalMetrics]) -> RetrievalMetrics:
    """对多条查询的检索指标取平均。"""
    n = len(metrics)
    if n == 0:
        return RetrievalMetrics()
    return RetrievalMetrics(
        precision=sum(m.precision for m in metrics) / n,
        recall=sum(m.recall for m in metrics) / n,
        f1=sum(m.f1 for m in metrics) / n,
        mrr=sum(m.mrr for m in metrics) / n,
        ndcg=sum(m.ndcg for m in metrics) / n,
        hit_rate=sum(m.hit_rate for m in metrics) / n,
    )


# ---------------------------------------------------------------------------
# 生成指标
# ---------------------------------------------------------------------------

@dataclass
class GenerationMetrics:
    bleu_1: float = 0.0
    bleu_2: float = 0.0
    bleu_3: float = 0.0
    bleu_4: float = 0.0
    rouge_1: float = 0.0
    rouge_2: float = 0.0
    rouge_l: float = 0.0
    exact_match: float = 0.0
    char_f1: float = 0.0
    answer_relevance: float = 0.0
    faithfulness: float = 0.0


def _bleu_n(hypothesis: List[str], reference: List[str], n: int) -> float:
    """单条 BLEU-n（字符级，含 brevity penalty）。"""
    hyp_ng = _ngrams(hypothesis, n)
    ref_ng = _ngrams(reference, n)
    if not hyp_ng:
        return 0.0
    clipped = sum(min(cnt, ref_ng[ng]) for ng, cnt in hyp_ng.items())
    precision = clipped / sum(hyp_ng.values())
    # brevity penalty
    bp = math.exp(1 - len(reference) / len(hypothesis)) if len(hypothesis) < len(reference) else 1.0
    return bp * precision


def bleu(hypothesis: str, reference: str) -> Tuple[float, float, float, float]:
    """返回 (BLEU-1, BLEU-2, BLEU-3, BLEU-4)，字符级。"""
    h = _tokenize(hypothesis)
    r = _tokenize(reference)
    if not h or not r:
        return 0.0, 0.0, 0.0, 0.0
    scores = []
    for n in range(1, 5):
        b = _bleu_n(h, r, n)
        scores.append(b)
    return tuple(scores)  # type: ignore[return-value]


def _lcs_length(a: List[str], b: List[str]) -> int:
    """最长公共子序列长度（DP）。"""
    m, n = len(a), len(b)
    # 空间优化：滚动数组
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[n]


def rouge_n(hypothesis: str, reference: str, n: int) -> float:
    """ROUGE-N F1（字符级）。"""
    h = _tokenize(hypothesis)
    r = _tokenize(reference)
    hyp_ng = _ngrams(h, n)
    ref_ng = _ngrams(r, n)
    overlap = sum(min(cnt, ref_ng[ng]) for ng, cnt in hyp_ng.items())
    if overlap == 0:
        return 0.0
    precision = overlap / max(sum(hyp_ng.values()), 1)
    recall = overlap / max(sum(ref_ng.values()), 1)
    return 2 * precision * recall / (precision + recall)


def rouge_l(hypothesis: str, reference: str) -> float:
    """ROUGE-L F1（基于 LCS，字符级）。"""
    h = _tokenize(hypothesis)
    r = _tokenize(reference)
    lcs = _lcs_length(h, r)
    if lcs == 0:
        return 0.0
    p = lcs / max(len(h), 1)
    rec = lcs / max(len(r), 1)
    return 2 * p * rec / (p + rec)


def exact_match(hypothesis: str, reference: str) -> float:
    """精确匹配（去除空白后比较）。"""
    return float(re.sub(r"\s+", "", hypothesis) == re.sub(r"\s+", "", reference))


def char_f1(hypothesis: str, reference: str) -> float:
    """字符级 F1（基于字符集合重叠）。"""
    h = Counter(_tokenize(hypothesis))
    r = Counter(_tokenize(reference))
    common = sum((h & r).values())
    if common == 0:
        return 0.0
    p = common / max(sum(h.values()), 1)
    rec = common / max(sum(r.values()), 1)
    return 2 * p * rec / (p + rec)


def answer_relevance(answer: str, query: str) -> float:
    """答案相关性：query 关键词在 answer 中的覆盖率（字符级）。"""
    q_tokens = set(_tokenize(query))
    a_tokens = set(_tokenize(answer))
    if not q_tokens:
        return 0.0
    return len(q_tokens & a_tokens) / len(q_tokens)


def faithfulness(answer: str, contexts: List[str]) -> float:
    """
    忠实度：answer 中的字符在检索上下文中的覆盖率。
    衡量生成内容是否"有据可查"。
    """
    if not contexts:
        return 0.0
    ctx_tokens = set(_tokenize(" ".join(contexts)))
    ans_tokens = _tokenize(answer)
    if not ans_tokens:
        return 0.0
    covered = sum(1 for t in ans_tokens if t in ctx_tokens)
    return covered / len(ans_tokens)


def compute_generation_metrics(
    hypothesis: str,
    reference: str,
    query: str = "",
    contexts: Optional[List[str]] = None,
) -> GenerationMetrics:
    """计算单条生成结果的全部指标。"""
    b1, b2, b3, b4 = bleu(hypothesis, reference)
    return GenerationMetrics(
        bleu_1=b1,
        bleu_2=b2,
        bleu_3=b3,
        bleu_4=b4,
        rouge_1=rouge_n(hypothesis, reference, 1),
        rouge_2=rouge_n(hypothesis, reference, 2),
        rouge_l=rouge_l(hypothesis, reference),
        exact_match=exact_match(hypothesis, reference),
        char_f1=char_f1(hypothesis, reference),
        answer_relevance=answer_relevance(hypothesis, query) if query else 0.0,
        faithfulness=faithfulness(hypothesis, contexts or []),
    )


def aggregate_generation_metrics(metrics: List[GenerationMetrics]) -> GenerationMetrics:
    """对多条生成指标取平均。"""
    n = len(metrics)
    if n == 0:
        return GenerationMetrics()
    fields = GenerationMetrics.__dataclass_fields__.keys()
    return GenerationMetrics(**{
        f: sum(getattr(m, f) for m in metrics) / n
        for f in fields
    })
