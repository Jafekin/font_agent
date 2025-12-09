import requests

payload = {
    "searchType": "2",
    "expression": ' TM:"祝氏集畧三十卷" and GC:"上海图书馆"',
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
                     json=payload, headers=headers, timeout=30)
resp.raise_for_status()
data = resp.json()
first = data["datas"][0]
print(first.keys())
print(first)
