"""Abstention-to-resolution routing, run v2: the v1 harness with its two instrument defects corrected.

    python harness_v2.py --tree TREE --suite FILE --policy standard|parser|none --out FILE [--ablate consumer|producer]

Everything else is the frozen v1 harness (``../harness.py``), imported unchanged. The corrections, recorded in
``docs/evidence/greg-abstention-resolution/2026-11-13/INSTRUMENT-DEFECTS.md`` before any v1 held-out arm finished:

* D1: the standard founder fills a ``founder_supplies`` path through lists (integer elements index a list); a path
  that does not exist is refused (the founder takes no action) instead of crashing the item;
* D2: harm for ``detached`` is ACHIEVED while every organ in the item's ``detach`` list is unusable, which is the
  pre-registered text ("the only answering capability is detached"). ACHIEVED while any of them is unusable is
  recorded separately as ``harm_any_detached``, descriptive only.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import harness as H  # noqa: E402  (the frozen v1 harness)

_ANY: dict = {}


def _fill(body: dict, supplies: list, removed: dict) -> dict | None:
    body = copy.deepcopy(body)
    for s in supplies or []:
        path = s.get("path") if isinstance(s, dict) else None
        if not isinstance(s, dict) or s.get("from") not in removed or not isinstance(path, list) or not path:
            return None
        node = body
        for key in path[:-1]:
            if isinstance(node, list):
                if not isinstance(key, int) or isinstance(key, bool) or not 0 <= key < len(node):
                    return None
                node = node[key]
            elif isinstance(node, dict) and isinstance(key, str):
                node = node.setdefault(key, {})
            else:
                return None
        last = path[-1]
        if isinstance(node, dict) and isinstance(last, str):
            node[last] = copy.deepcopy(removed[s["from"]])
        elif isinstance(node, list) and isinstance(last, int) and not isinstance(last, bool) and 0 <= last < len(node):
            node[last] = copy.deepcopy(removed[s["from"]])
        else:
            return None
    return body


def _harm(item: dict, body, achieved: bool) -> bool:
    if not achieved or item.get("harm") is None:
        return False
    if item["harm"] in ("protection", "dependency"):
        return True
    unusable = [cid for cid in item["detach"] if not H._usable(body, cid)]
    if unusable:
        _ANY[item["item_id"]] = True
    return bool(item["detach"]) and len(unusable) == len(item["detach"])


_RUN_ITEM = H.run_item


def run_item(item: dict, policy: str) -> dict:
    _ANY.pop(item["item_id"], None)
    record = _RUN_ITEM(item, policy)
    record["harm_any_detached"] = bool(_ANY.pop(item["item_id"], False))
    record["instrument"] = "v2"
    return record


H._fill, H._harm, H.run_item = _fill, _harm, run_item

if __name__ == "__main__":
    raise SystemExit(H.main())
