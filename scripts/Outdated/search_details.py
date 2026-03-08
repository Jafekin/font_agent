'''
Author        陈佳辉 1946847867@qq.com
Date          2025-12-09 19:57:41
LastEditTime  2025-12-10 18:44:05
Description   

'''
from __future__ import annotations
import json
from functools import lru_cache
from urllib.parse import urljoin

import requests

EDITION_TYPE_MAP = {
    "ke-ben": "刻本",
    "chao-ben": "抄本",
    "yin-ben": "印本",
}

DATA_BASE_URL = "http://data.library.sh.cn/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
JSONLD_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/ld+json",
}


def _normalize_vocab_value(value: str | None) -> str:
    if not value:
        return "—"
    if "/" in value:
        return value.rsplit("/", 1)[-1]
    return value


def fetch_graph(uri: str):
    """Return the @graph list from the JSON-LD representation of the instance."""
    resp = requests.get(uri, headers=JSONLD_HEADERS, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("@graph", [])


def pick_instance_node(graph):
    """Locate the node describing the pmb:Instance entity."""
    for node in graph:
        node_type = node.get("@type")
        if node_type == "pmb:Instance":
            return node
        if isinstance(node_type, list) and "pmb:Instance" in node_type:
            return node
    raise RuntimeError("pmb:Instance node not found in @graph")


def _extract_title(instance: dict) -> str:
    title = instance.get('title')
    if isinstance(title, list):
        def pick(lang: str) -> str:
            for item in title:
                if isinstance(item, dict) and item.get('@language') == lang:
                    return item.get('@value', '')
            return ''

        for lang in ("chs", "cht", "zh-pny"):
            value = pick(lang)
            if value:
                return value
        for item in title:
            if isinstance(item, dict) and item.get('@value'):
                return item['@value']
        return ""
    if isinstance(title, dict):
        return title.get('@value', '')
    return title or ""


def _extract_edition_label(edition: str | None) -> str:
    code = _normalize_vocab_value(edition)
    return EDITION_TYPE_MAP.get(code, code)


def _absolute_uri(resource_id: str) -> str:
    if resource_id.startswith("http://") or resource_id.startswith("https://"):
        return resource_id
    return urljoin(DATA_BASE_URL, resource_id.lstrip("/"))


@lru_cache(maxsize=128)
def _fetch_temporal_label(resource_id: str) -> str:
    if resource_id.startswith("_"):
        return ""
    uri = _absolute_uri(resource_id)
    resp = requests.get(uri, headers=JSONLD_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    graph = data.get("@graph") or []
    for node in graph:
        label = node.get("label") or node.get(
            "prefLabel") or node.get("rdfs:label")
        if isinstance(label, dict):
            return label.get("@value", "")
        if isinstance(label, str) and label.strip():
            return label.strip()
    label = data.get("label")
    if isinstance(label, dict):
        return label.get("@value", "")
    return label or ""


def _resolve_temporal_labels(instance: dict) -> str:
    temporal_entries = instance.get("temporal") or []
    labels: list[str] = []
    for entry in temporal_entries:
        identifier = ""
        if isinstance(entry, str):
            identifier = entry
        elif isinstance(entry, dict):
            identifier = entry.get("@id", "")
        if identifier.startswith("_") or not identifier:
            continue
        label = _fetch_temporal_label(identifier)
        if label:
            labels.append(label)
    return "；".join(labels) if labels else "—"


def _format_responsibility(instance: dict) -> str:
    contributions = instance.get('contributions') or []
    parts = []
    for c in contributions:
        label = (c.get('label') or '').strip()
        role = (c.get('role') or '').strip()
        if label and role:
            parts.append(f"{label} {role}")
        elif label:
            parts.append(label)
    if parts:
        return '；'.join(parts)

    creator_line = instance.get('dc:creator') or instance.get('creator')
    return creator_line or '—'


def format_instance(instance: dict) -> str:
    title = _extract_title(instance) or instance.get('label') or '—'
    classification = (
        instance.get('pmb:classification')
        or instance.get('classFullName')
        or instance.get('classification')
        or '—'
    )
    volume = instance.get('volumeName') or instance.get('volume') or '—'
    edition_label = instance.get('label', '—')
    edition_type = _extract_edition_label(instance.get('edition'))
    identifier = instance.get('identifier') or instance.get(
        'dc:identifier') or '—'
    extent = instance.get('extent') or '—'
    dimensions = instance.get('dimensions') or '—'
    plate_frame = instance.get('plateFrame') or '—'
    plate_size = instance.get('plateFrameSize') or '—'
    elephant_nose = instance.get('elephantNose') or '—'
    fish_tail = instance.get('fishTail') or '—'
    temporal_value = instance.get('temporalValue', '—')
    temporal_begin = instance.get('temporalBegin', '—')
    temporal_end = instance.get('temporalEnd', '—')
    dc_type = instance.get('dcType') or instance.get('dc:type') or '—'
    desc = instance.get('description') or instance.get('descripttion') or ''
    desc_line = desc.strip() if isinstance(desc, str) else ''

    responsibility = _format_responsibility(instance)
    temporal_labels = _resolve_temporal_labels(instance)
    source = instance.get('sourceLabel') or instance.get(
        'source') or '上海图书馆古籍数据库'
    source_display = '上海图书馆古籍数据库' if source.startswith('gj/') else source

    lines = [
        f"標題：{title}",
        f"所有責任者：{responsibility}",
        f"分類：{classification}",
        f"朝代：{temporal_labels}",
        f"版本：{edition_label}",
        f"版本類型：{edition_type}",
        f"版本時間：{temporal_value}",
        f"冊數：{extent}",
        f"尺寸：{dimensions}",
        f"書口：{elephant_nose}",
        f"魚尾：{fish_tail}",
        f"邊欄：{plate_frame}",
        f"版框尺寸：{plate_size}",
        f"卷別：{volume}",
        f"編號：{identifier}",
        f"類型：{dc_type}",
        f"提要：{desc_line if desc_line else '—'}",
        f"來源：{source_display}",
    ]

    return "\n".join(lines)


def get_details(search_txt: str):
    payload = {
        "searchType": "2",
        "expression": f'TM:"{search_txt}" and GC:"上海图书馆"',
        "cdtn": [
            {"logic": "", "field": "TM", "value": "祝氏集畧三十卷", "type": "0"},
            {"logic": "and", "field": "GC", "value": "上海图书馆", "type": "0"}
        ],
        "facet": {},
        "secondCdtn": "",
        "pager": {"pageth": 1, "pageSize": 10},
        "sorts": {"title": "1"},
        "hasFacet": True
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://gj.library.sh.cn/unionCatalogue/search?searchType=adv",
        "Origin": "https://gj.library.sh.cn",
    }

    resp = requests.post("https://gj.library.sh.cn/es/api/gjmult/inst",
                         json=payload, headers=headers, timeout=30, verify=False)

    resp.raise_for_status()
    data = resp.json()
    first = data["datas"][0]

    # print(first.keys())
    # print(first)
    # print(first['uri'])
    # tail = first['uri'].rstrip("/").split("/")[-1]
    # print(tail)

    # target_url = f"https://gj.library.sh.cn/unionCatalogue/work/list#uri=http://data.library.sh.cn/gj/resource/instance/{tail}"
    # target_headers = {
    #     "User-Agent": headers["User-Agent"],
    #     "Referer": "https://gj.library.sh.cn/unionCatalogue/search?searchType=adv",
    # }

    # target_resp = requests.post(target_url, headers=target_headers, timeout=30)
    # target_resp.raise_for_status()
    # html = target_resp.text
    # print(html)

    uri = first['uri']
    graph = fetch_graph(uri)
    instance = pick_instance_node(graph)
    print(f"Fetched instance data for {uri}\n")
    print(format_instance(instance))
    # print(instance)


if __name__ == "__main__":
    get_details("祝氏集畧三十卷")
