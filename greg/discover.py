"""Discovery by intention: from an outcome in plain words to the machinery that can actually help.

The founder should not need to know that "sell something and reconcile the money" means Foundry #37, #38, #39 and #54,
or which mission template drafts it. This module ranks three kinds of real, installed things against the words:

  mission paths       GREG's mission templates (drafted from words, reviewed, signed)
  capabilities        GREG's registered capability manifests (what a signed mission may use)
  Foundry systems     the 55 numbered systems, with their contract state (COMPLETE / PARTIAL) and gap

Ranking is Okapi BM25 over each item's own declared text (name, description, acceptance criteria, interface,
control surfaces), with light suffix stemming. It is lexical retrieval, stated as such: it finds what the words name;
it does not judge feasibility. Every result carries its truthful state, and the matched terms say why it ranked.
Nothing here plans, attaches or runs anything.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = frozenset("a an and are as at be by for from i in into is it its me my of on or the to with what which who how "
                 "can cannot do does this that these those want need please greg you your our we will would should "
                 "so get make help one all any some also just then there them they their out up take through find "
                 "every against".split())
SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ied", "ed", "es", "s", "ly")
# A small, disclosed bridge from founder words to the vocabulary the systems declare (weighted at half a match).
SYNONYMS = {"sell": ("offer", "order", "commerce", "marketplace"), "buy": ("order", "commerce", "payment"),
            "customer": ("buyer", "order", "commerce"), "revenue": ("accounting", "ledger", "finance"),
            "money": ("payment", "accounting", "finance"), "pay": ("payment", "settlement"),
            "checksum": ("sha256", "hash", "digest"), "isolat": ("sandbox", "isolation", "confin"),
            "untrust": ("sandbox", "isolation"), "post": ("publish", "media"),
            "audience": ("community", "distribution", "follower"), "video": ("media",), "image": ("media",),
            "schedul": ("shift", "schedule"), "plan": ("lp", "optimiz"), "fund": ("treasury", "finance")}


def stem(word: str) -> str:
    for suffix in SUFFIXES:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix in ("ies", "ied") else "")
    return word


def tokens(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 1]


@lru_cache(maxsize=1)
def corpus() -> tuple:
    import yaml
    from foundry.arsenal import technology
    from foundry.systems import ALTERNATES, SYSTEMS
    from greg import templates
    from greg.capabilities import BUILTINS
    items = []
    for name, fn in sorted(templates.TEMPLATES.items()):
        doc = (fn.__doc__ or "").strip()
        items.append({"kind": "mission path", "id": name, "title": name.replace("-", " "),
                      "text": f"{name.replace('-', ' ')} {doc}", "state": "drafted from your words, then you sign",
                      "how": "Command: describe the outcome; GREG drafts this mission for review"})
    for cid, (manifest, _) in sorted(BUILTINS.items()):
        items.append({"kind": "capability", "id": cid, "title": manifest.description[:120],
                      "text": f"{cid.replace('.', ' ').replace('_', ' ')} {manifest.function.replace('.', ' ')} "
                              f"{manifest.description}",
                      "state": None, "consequence": manifest.consequence_class,
                      "how": "used inside a signed mission's envelope"})
    rows = yaml.safe_load((ROOT / "foundry/completion.yaml").read_text())
    for sid in range(1, 56):
        spec, row = technology(sid), rows.get(sid, {})
        acceptance = " ".join(row.get("acceptance") or [])
        surfaces = " ".join(spec.control_surfaces or ())
        modules = " ".join([SYSTEMS.get(sid) or "", *ALTERNATES.get(sid, ())]).replace("_", " ")
        items.append({"kind": "Foundry system", "id": f"#{sid}", "title": spec.name,
                      "text": f"{spec.name} {spec.category} {surfaces} {modules} {acceptance} {row.get('interface') or ''}",
                      "state": row.get("state", "UNKNOWN"), "gap": (row.get("gap") or "")[:240],
                      "how": row.get("interface") or "foundry.query / foundry.apply inside a signed mission"})
    docs = [Counter(tokens(i["text"])) for i in items]
    return tuple(items), tuple(docs)


def discover(text: str, *, limit: int = 8, kinds: tuple[str, ...] | None = None) -> list[dict]:
    base = list(dict.fromkeys(tokens(text)))
    if not base:
        return []
    weights = {t: 1.0 for t in base}
    for t in base:
        for key, extra in SYNONYMS.items():
            if t.startswith(key):
                for e in extra:
                    weights.setdefault(stem(e), 0.5)
    query = list(weights)
    items, docs = corpus()
    n = len(docs)
    avg = sum(sum(d.values()) for d in docs) / n
    df = Counter(t for d in docs for t in set(d))
    k1, b = 1.2, 0.75
    scored = []
    for item, d in zip(items, docs):
        if kinds and item["kind"] not in kinds:
            continue
        length = sum(d.values())
        score, matched = 0.0, []
        for t in query:
            tf = d.get(t, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += weights[t] * idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg))
            matched.append(t)
        if score > 0:
            scored.append((score, item, matched))
    scored.sort(key=lambda x: (-x[0], x[1]["kind"], x[1]["id"]))
    return [{**{k: v for k, v in item.items() if k != "text"}, "score": round(score, 3), "matched": matched}
            for score, item, matched in scored[:limit]]
