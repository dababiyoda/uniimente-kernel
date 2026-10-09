"""Untrusted data plane: web pages, emails, community replies, documents, model output.

External content is DATA. It is retained with provenance so it can inform
missions (community influence is real: signals are evidence a mission may read),
but it can never become a command: only an Ed25519-signed founder envelope in
the inbox is a command, and nothing here writes to the inbox or grants scope.

Instruction-shaped text is flagged and quarantined from any planner that would
otherwise quote it as guidance. The flag is a heuristic aid; the guarantee is
structural (the authority plane accepts only signed founder commands).
"""
from __future__ import annotations

import hashlib
import re

from greg.journal import Journal, iso, utcnow

INSTRUCTION_PATTERNS = [
    r"ignore (all |your |the )?(previous|prior|above) instructions",
    r"disregard (the |your )?(system|previous|prior)",
    r"you are now", r"new instructions?:", r"system prompt",
    r"(send|reveal|print|exfiltrate).{0,40}(secret|password|api key|token|credential|private key)",
    r"(grant|give|raise).{0,30}(permission|access|authority|budget)",
    r"run (this|the following) (command|code)", r"curl .*\|\s*(sh|bash)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in INSTRUCTION_PATTERNS]
MAX_RETAINED = 8000


def instruction_shaped(text: str) -> list[str]:
    return [p.pattern for p in _COMPILED if p.search(text)]


def ingest(journal: Journal, *, source: str, content: str, channel: str) -> dict:
    """Retain one external item as inert evidence. Never a command, never authority."""
    if not isinstance(content, str):
        raise ValueError("external content must be text")
    flags = instruction_shaped(content)
    record = {"source": source[:500], "channel": channel[:100],
              "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
              "content": content[:MAX_RETAINED], "truncated": len(content) > MAX_RETAINED,
              "trust": "untrusted", "instruction_flags": flags, "quarantined": bool(flags),
              "may_command": False, "may_grant": False, "at": iso(utcnow())}
    journal.record("external.ingested", record, key=[source, record["content_sha256"]], sensitivity="confidential")
    return record


def community_signals(journal: Journal, channel: str) -> dict:
    """Aggregate non-quarantined community items into mission-readable evidence."""
    items = [e.payload for e in journal.replay("external.ingested") if e.payload["channel"] == channel]
    usable = [i for i in items if not i["quarantined"]]
    return {"channel": channel, "items": len(items), "usable": len(usable),
            "quarantined": len(items) - len(usable),
            "sources": sorted({i["source"] for i in usable})[:100]}


# Directive 2026-10-07 section 23: community signals inform needs, preferences, failures, demand, corrections,
# quality, cultural context and opportunities as TYPED EVIDENCE. Popularity is never authority: no count,
# vote or engagement figure here can change a priority, a mission or a permission; a priority changes only
# after outcome evaluation and a founder decision. Minority reports are preserved, never averaged away.
SIGNAL_KINDS = {
    "need": r"\b(i|we) (need|want|wish|require)|\bmissing\b|\bcan'?t find\b",
    "preference": r"\b(prefer|rather|would like|favourite|favorite)\b",
    "failure": r"\b(broken|bug|fails?|failed|error|crash(es|ed)?|doesn'?t work|stopped working)\b",
    "demand": r"\b(would (pay|buy)|take my money|price|pricing|subscribe|waitlist)\b",
    "correction": r"\b(actually|incorrect|wrong|not true|mistake|correction|misleading)\b",
    "quality": r"\b(quality|slow|fast|reliable|unreliable|confusing|clear|excellent|terrible)\b",
    "cultural_context": r"\b(in our (community|culture|country)|where i live|locally|tradition)\b",
    "opportunity": r"\b(opportunity|what if|could also|idea|integrat(e|ion)|partner)\b",
}
_KINDS = {k: re.compile(v, re.IGNORECASE) for k, v in SIGNAL_KINDS.items()}


def _normal(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def community_evidence(journal: Journal, channel: str, *, campaign_sources: int = 3) -> dict:
    """Typed, manipulation-resistant community evidence with preserved minority reports. Never authority.

    * one source carries one unit of weight per claim, whatever its volume (brigading by repetition fails);
    * identical normalised text from ``campaign_sources`` or more sources is flagged as a possible
      coordinated campaign and its cluster counts as one unit;
    * per kind, every distinct claim is kept with its support; claims below the most-supported one are the
      minority reports, listed explicitly;
    * classification is a keyword heuristic, labelled as such.
    """
    items = [e.payload for e in journal.replay("external.ingested")
             if e.payload["channel"] == channel and not e.payload["quarantined"]]
    clusters: dict[str, dict] = {}
    for item in items:
        key = hashlib.sha256(_normal(item["content"]).encode()).hexdigest()
        c = clusters.setdefault(key, {"text": item["content"][:500], "sources": set(), "first_at": item["at"],
                                      "kinds": sorted(k for k, rx in _KINDS.items() if rx.search(item["content"]))})
        c["sources"].add(item["source"])
    by_kind: dict[str, list] = {k: [] for k in SIGNAL_KINDS}
    flagged = []
    for key, c in sorted(clusters.items()):
        campaign = len(c["sources"]) >= campaign_sources
        weight = 1 if campaign else len(c["sources"])
        if campaign:
            flagged.append({"claim": c["text"][:200], "sources": len(c["sources"]),
                            "flag": "COORDINATED_CAMPAIGN_SUSPECTED", "counted_as": 1})
        record = {"claim": c["text"], "support_sources": weight, "raw_sources": len(c["sources"]),
                  "first_at": c["first_at"], "cluster": key[:16], "campaign_suspected": campaign}
        for kind in c["kinds"] or ["unclassified"]:
            by_kind.setdefault(kind, []).append(record)
    kinds = {}
    for kind, records in by_kind.items():
        if not records:
            continue
        records.sort(key=lambda r: (-r["support_sources"], r["claim"]))
        top = records[0]["support_sources"]
        kinds[kind] = {"claims": records, "minority_reports": [r for r in records if r["support_sources"] < top]}
    return {"channel": channel, "items": len(items), "distinct_claims": len(clusters), "by_kind": kinds,
            "coordination_flags": flagged, "classification": "keyword heuristic; a person may relabel",
            "authority": "none: popularity, votes and engagement never change a priority, mission or permission",
            "may_change_priority": "only after outcome evaluation and a founder decision",
            "trust": "untrusted"}
