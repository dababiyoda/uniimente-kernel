#!/usr/bin/env python3
"""Project the planning graph into the required artifact set.

Every file written here is a *projection*. The graph is the only source of
planning truth; these outputs are derived, deterministic, and disposable. That
is what stops forty planning documents from drifting against one another: a
decision changes once, in the graph, and every dependent artifact is regenerated.

Determinism is a hard requirement, not an aspiration. Nothing in a rendered
artifact may vary between runs — no timestamps, no dict iteration order, no
absolute paths. ``planning/tests/test_idempotence.py`` regenerates everything
and fails if a single byte moves.

Usage:
    python planning/compiler/render.py            # write artifacts
    python planning/compiler/render.py --check    # verify committed == regenerated
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from planning.compiler.model import PlanningGraph, load_graph, repo_root  # noqa: E402

DOCS_REL = os.path.join("docs", "planning", "uniimente_v1")
ARTIFACTS_REL = os.path.join("artifacts", "planning", "uniimente_v1")

GENERATED_BANNER = "<!-- GENERATED FILE — DO NOT EDIT BY HAND -->"


def _provenance(graph: PlanningGraph, source: str) -> str:
    """Header stamped onto every projection so drift is self-reporting."""
    return (
        f"{GENERATED_BANNER}\n"
        f"<!-- source: planning/graph/nodes/ via planning/compiler/render.py -->\n"
        f"<!-- graph-digest: {graph.digest()} -->\n"
        f"<!-- projection: {source} -->\n"
    )


def _fmt_value(value, indent: int = 0) -> str:
    """Render a YAML-loaded value as readable Markdown, order-stably."""
    pad = "  " * indent
    if isinstance(value, dict):
        lines = []
        for key in value:  # insertion order preserved from YAML; stable on disk
            rendered = _fmt_value(value[key], indent + 1)
            if "\n" in rendered:
                lines.append(f"{pad}- **{key}**:\n{rendered}")
            else:
                lines.append(f"{pad}- **{key}**: {rendered.strip()}")
        return "\n".join(lines)
    if isinstance(value, list):
        return "\n".join(f"{pad}- {_fmt_value(v, indent + 1).strip()}" for v in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _node_markdown(node) -> str:
    lines = [f"### `{node.id}` — {node.title}", ""]
    lines.append(f"**Evidence:** `{node.evidence_status}`")
    if node.evidence_refs:
        for ref in node.evidence_refs:
            bits = [f"`{ref.repo}` @ `{ref.sha[:12]}`"]
            if ref.path:
                bits.append(f"path `{ref.path}`")
            if ref.symbol:
                bits.append(f"→ {ref.symbol}")
            if ref.command:
                bits.append(f"via `{ref.command}`")
            if ref.note:
                bits.append(f"({ref.note})")
            lines.append(f"- {' · '.join(bits)}")
    else:
        lines.append("- _no evidence reference — this node is explicitly unresolved_")
    lines.append("")
    body = {k: v for k, v in node.body.items() if k != "refs"}
    if body:
        lines.append(_fmt_value(body))
        lines.append("")
    if node.body.get("refs"):
        refs = ", ".join(f"`{r}`" for r in node.body["refs"])
        lines.append(f"_Relates to: {refs}_")
        lines.append("")
    return "\n".join(lines)


class Projection:
    """One artifact pair: a Markdown view and a JSON view of selected nodes."""

    def __init__(self, name: str, title: str, kinds: list[str], preamble: str = ""):
        self.name = name
        self.title = title
        self.kinds = kinds
        self.preamble = preamble

    def select(self, graph: PlanningGraph) -> list:
        out = []
        for kind in self.kinds:
            out.extend(graph.of_kind(kind))
        return out

    def markdown(self, graph: PlanningGraph) -> str:
        nodes = self.select(graph)
        parts = [_provenance(graph, self.name), "", f"# {self.title}", ""]
        if self.preamble:
            parts.extend([self.preamble.strip(), ""])
        parts.append(
            f"**{len(nodes)} nodes** projected from graph digest "
            f"`{graph.digest()[:16]}`. Regenerate with "
            "`python planning/compiler/render.py`."
        )
        parts.append("")
        for kind in self.kinds:
            of_kind = graph.of_kind(kind)
            if not of_kind:
                continue
            parts.append(f"## {kind.replace('_', ' ')} ({len(of_kind)})")
            parts.append("")
            for node in of_kind:
                parts.append(_node_markdown(node))
        return "\n".join(parts).rstrip() + "\n"

    def json_payload(self, graph: PlanningGraph) -> str:
        payload = {
            "projection": self.name,
            "title": self.title,
            "graph_digest": graph.digest(),
            "node_count": len(self.select(graph)),
            "nodes": [n.to_dict() for n in self.select(graph)],
        }
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


PROJECTIONS = [
    Projection(
        name="INSPECTION_TRUTH",
        title="SP-0 — Inspection Truth Freeze",
        kinds=[
            "repository",
            "repository_unavailable",
            "source_unavailable",
            "pull_request",
            "finding",
            "discrepancy",
            "assumption",
        ],
        preamble="""
Measured 2026-08-08 against live repositories and the GitHub API. This is the
frozen evidence base for the whole round: **no recommendations appear here.**

Where the canonical prompt and the repositories disagree, both readings are
recorded and the disagreement is itself a node. Sources that could not be
reached are listed as unavailable and may never be cited as evidence — a
mechanical check (`unavailable_sources_not_cited_as_evidence`) enforces this
rather than trusting the author.
""",
    ),
    Projection(
        name="FOUNDER_INTENT_LEDGER",
        title="Founder Intent Ledger — Protected Horizon",
        kinds=["protected_intent"],
        preamble="""
The Founder-Horizon Override frozen as protected intent nodes, per the canonical
prompt's execution command: *"First freeze the Founder-Horizon Override into the
planning graph as protected intent nodes."*

These may be classified, translated and routed. They may not be weakened,
deleted, or silently superseded. Override §2 is explicit: never convert *"not
implemented today"* into *"not actually intended."*

Source: `UNIIMENTE_SUPER_PLANNING_ROUND_MOST_CURRENT.{md,txt}`, both byte-identical
at sha256 `1fd49e07437d53c6ac708e4a3871272acd1fd2a1507acc95bbd0599de7468c9e`,
verified by execution against the founder's stated hash.
""",
    ),
]


def render_all(graph: PlanningGraph, root: str) -> dict[str, str]:
    """Return {absolute_path: content} for every artifact. Pure — no writes."""
    out: dict[str, str] = {}
    for projection in PROJECTIONS:
        md = os.path.join(root, DOCS_REL, f"{projection.name}.md")
        js = os.path.join(root, ARTIFACTS_REL, f"{projection.name}.json")
        out[md] = projection.markdown(graph)
        out[js] = projection.json_payload(graph)
    # The graph itself, projected verbatim, so the model travels with its outputs.
    out[os.path.join(root, ARTIFACTS_REL, "PLANNING_GRAPH.json")] = (
        graph.canonical_json() + "\n"
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed artifacts match a fresh render; write nothing",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    graph = load_graph()
    rendered = render_all(graph, root)

    if args.check:
        drifted, missing = [], []
        for path, content in sorted(rendered.items()):
            rel = os.path.relpath(path, root)
            if not os.path.exists(path):
                missing.append(rel)
            elif open(path, encoding="utf-8").read() != content:
                drifted.append(rel)
        if missing or drifted:
            for rel in missing:
                print(f"MISSING: {rel}")
            for rel in drifted:
                print(f"DRIFTED: {rel} (hand-edited, or graph changed without re-render)")
            print(f"\nFAIL: {len(missing)} missing, {len(drifted)} drifted")
            return 1
        print(f"PASS: all {len(rendered)} artifacts match the graph at {graph.digest()[:16]}")
        return 0

    for path, content in sorted(rendered.items()):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        print(f"wrote {os.path.relpath(path, root)}")
    print(f"\n{len(rendered)} artifacts from graph digest {graph.digest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
