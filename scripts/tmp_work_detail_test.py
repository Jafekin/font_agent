import json
from pprint import pprint

import requests


DEFAULT_URI = "http://data.library.sh.cn/gj/resource/instance/pcc455j1xxds68xx"


def fetch_graph(uri: str):
    """Return the @graph list from the JSON-LD representation of the instance."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/ld+json",
    }
    resp = requests.get(uri, headers=headers, timeout=15)
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


def main(uri: str):
    graph = fetch_graph(uri)
    instance = pick_instance_node(graph)
    print(f"Fetched instance data for {uri}\n")
    pprint(instance)
    extra_nodes = [n for n in graph if n is not instance]
    if extra_nodes:
        print("\nOther graph nodes (truncated):")
        print(json.dumps(extra_nodes[:3], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(DEFAULT_URI)
