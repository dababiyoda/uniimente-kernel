"""Untrusted data plane: web pages, emails, community replies, documents, model output.

External content is DATA. It is retained with provenance so it can inform
missions (community influence is real: signals are evidence a mission may read),
but it can never become a command: only an Ed25519-signed founder envelope in
the inbox is a command, and nothing here writes to the inbox or grants scope.

Instruction-shaped text is flagged and quarantined from any planner that would
otherwise quote it as guidance. The flag is a heuristic aid; the guarantee is
structural (the authority plane accepts only signed founder commands).

Patterns are matched on every way the text can be read, folded by
identity.text.fold: what a person sees (terminal escape sequences and invisible
code points removed, NFKC, Cyrillic/Greek/Armenian look-alike letters folded,
case-folded, whitespace runs and line breaks collapsed to one space; a
whitespace-like control is read both as nothing and as a break), and what a
model may read but a person does not see (tag characters read as the ASCII they
shadow, a run of variation selectors as the bytes it encodes, an escape
sequence's own text). The invisible set (identity.text.INVISIBLE) is derived
from Unicode properties, not hand-listed. The stored content and its
content_sha256 are always of the original.

Quarantine follows PR #13's scoring (sdk-python/uniimente_kernel/prompt_firewall.py:
0.4 per instruction pattern, 0.3 for invisible characters, 0.2 for a role marker,
blocked at 0.4): an instruction pattern quarantines; concealing invisible
characters together with a role marker quarantine; either of those alone only
flags. Ordinary text therefore stays usable evidence: a "System: Ubuntu 22.04" or
"Tool: pytest" header line, ANSI-coloured logs, ZWNJ in Persian or Indic words,
ZWJ in emoji sequences, emoji presentation and ideographic variation selectors,
subdivision flags, a leading BOM, a soft hyphen inside a word, and bidi marks in
right-to-left text. Those orthographic uses are not counted as concealing; every
other invisible code point is. Role markers cover line-leading "system:" (also
as a markdown heading, bold or block quote), "[system]"/"[INST]", ChatML and
similar special tokens ("<|im_start|>"), and Llama "<<SYS>>".
Mechanism from PR #13 sdk-python/uniimente_kernel/prompt_firewall.py
(_INVISIBLE_RE, _ROLE_MARKER_RE, sanitize, scan); GREG's outbound ask screen
(greg/asks.py) uses the same character set.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from greg.journal import Journal, iso, utcnow
from identity.text import INVISIBLE, VARIATION_SELECTORS, drop_invisible, fold

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
HIDDEN = "invisible-characters"
ROLE = "role-marker"

# Terminal escape sequences (ECMA-48, 7-bit forms): CSI, OSC up to BEL or ST, and the other two-byte escapes.
# A terminal draws none of their bytes, so a person reading a log sees only the text around them. The 8-bit
# C1 forms (U+009B, U+009D) are not recognised: in Unicode text they are just invisible controls.
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]"
                   r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
                   r"|\x1b[@-Z\\-_]")
# Invisible code points that some renderers draw as a break (VT, FF, FS..US, NEL): read both ways.
_BREAKS = re.compile("[" + "".join(re.escape(chr(cp)) for cp in sorted(INVISIBLE) if chr(cp).isspace()) + "]")
# Hidden text: tag characters U+E0020-E007E shadow ASCII; a run of variation selectors encodes bytes
# (VS1-16 = 0-15, VS17-256 = 16-255).
_SMUGGLED = re.compile("[\U000e0020-\U000e007e]+|[︀-️\U000e0100-\U000e01ef]{2,}")
_ROLES = r"(?:system|assistant|developer|tool)"
_ROLE_MARKER = re.compile(
    rf"^[ \t>]*(?:#{{1,6}}[ \t]*)?(?:\*\*|__|\*|_)?[ \t]*{_ROLES}[ \t]*(?:\*\*|__|\*|_)?[ \t]*:"
    rf"|^[ \t>]*\[[ \t]*/?(?:{_ROLES}|inst|sys)[ \t]*\]"
    r"|<\|[ \t]*(?:im_start|im_end|im_sep|endoftext|start_header_id|end_header_id|eot_id"
    r"|system|assistant|user|developer|tool)[ \t]*\|>"
    r"|<<[ \t]*/?sys[ \t]*>>", re.MULTILINE)
# Scripts whose orthography uses ZWNJ/ZWJ between letters: Arabic (Persian, Urdu), Syriac, Thaana, N'Ko,
# the Indic scripts and Sinhala, Myanmar, Khmer, Mongolian, Arabic presentation forms, Hanifi Rohingya,
# Brahmi to Grantha.
_JOINING_SCRIPTS = ((0x0600, 0x08FF), (0x0900, 0x0DFF), (0x1000, 0x109F), (0x1780, 0x18AF), (0xA8E0, 0xA8FF),
                    (0xA9E0, 0xA9FF), (0xAA60, 0xAA7F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFC), (0x10D00, 0x10D3F),
                    (0x11000, 0x1135F))
_EMOJI_TAG_SEQUENCE = re.compile("\U0001f3f4[\U000e0030-\U000e0039\U000e0061-\U000e007a]{2,6}\U000e007f")
_KEYCAP = re.compile("[0-9#*][︎️]⃣")


def visible(text: str) -> str:
    """What a reader sees: escape sequences and invisible characters removed, NFKC (invisible removed again
    after). Layout (spaces, tabs, line breaks) is kept."""
    return drop_invisible(unicodedata.normalize("NFKC", drop_invisible(_ANSI.sub("", text))))


def _unsmuggle(match: re.Match) -> str:
    run = match.group(0)
    if 0xE0020 <= ord(run[0]) <= 0xE007E:
        return "".join(chr(ord(ch) - 0xE0000) for ch in run)
    data = bytes(ord(ch) - 0xFE00 if ord(ch) <= 0xFE0F else ord(ch) - 0xE0100 + 16 for ch in run)
    return data.decode("utf-8", errors="ignore")


def _readings(text: str) -> set[str]:
    """Each way ``text`` may be read, folded, line structure kept (for role markers)."""
    shown = _ANSI.sub("", text)
    readings = {fold(shown), fold(_BREAKS.sub("\n", shown))}
    if _SMUGGLED.search(text) or _ANSI.search(text):
        readings.add(fold(_SMUGGLED.sub(_unsmuggle, text)))      # the escape sequences' own text kept
    return readings


def _joining_letter(ch: str) -> bool:
    return bool(ch) and unicodedata.category(ch)[0] in "LM" and \
        any(low <= ord(ch) <= high for low, high in _JOINING_SCRIPTS)


def _pictograph(ch: str) -> bool:
    return bool(ch) and (unicodedata.category(ch) == "So" or 0x1F000 <= ord(ch) <= 0x1FAFF)


def _pictograph_before(text: str, i: int) -> bool:
    i -= 1
    while i >= 0 and (text[i] in "︎️" or 0x1F3FB <= ord(text[i]) <= 0x1F3FF):
        i -= 1
    return i >= 0 and _pictograph(text[i])


def concealing(text: str) -> list[str]:
    """Invisible code points that conceal, as 'U+XXXX'. Not counted: terminal escape sequences, and the
    orthographic uses ordinary text needs (see the module docstring)."""
    text = _ANSI.sub("", text)
    exempt = {i for rx in (_EMOJI_TAG_SEQUENCE, _KEYCAP) for m in rx.finditer(text) for i in range(*m.span())}
    right_to_left = any(unicodedata.bidirectional(ch) in ("R", "AL") and unicodedata.category(ch)[0] == "L"
                        for ch in text)
    found = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if cp not in INVISIBLE or i in exempt:
            continue
        before = text[i - 1] if i else ""
        after = text[i + 1] if i + 1 < len(text) else ""
        if cp == 0x200D and _pictograph_before(text, i) and _pictograph(after):
            continue                                           # emoji ZWJ sequence
        if cp in (0x200C, 0x200D) and _joining_letter(before) and _joining_letter(after):
            continue                                           # ZWNJ/ZWJ inside a word that uses it
        if cp in VARIATION_SELECTORS and before and ord(before) > 0x7F and ord(before) not in INVISIBLE \
                and unicodedata.category(before)[0] in "LNPS" and not (after and ord(after) in VARIATION_SELECTORS):
            continue                                           # one selector after a non-ASCII base
        if (cp == 0xFEFF and i == 0) or (cp == 0xAD and before.isalpha() and after.isalpha()) \
                or (cp in (0x200E, 0x200F, 0x061C) and right_to_left):
            continue                                           # BOM, soft hyphen, bidi mark in RTL text
        found.append(f"U+{cp:04X}")
    return found


def instruction_shaped(text: str) -> list[str]:
    readings = _readings(text)
    collapsed = [" ".join(r.split()) for r in readings]
    flags = [p.pattern for p in _COMPILED if any(p.search(r) for r in collapsed)]
    if concealing(text):
        flags.append(HIDDEN)
    if any(_ROLE_MARKER.search(r) for r in readings):
        flags.append(ROLE)
    return flags


def quarantines(flags) -> bool:
    """An instruction pattern, or concealing characters together with a role marker. Either alone flags."""
    flags = set(flags)
    return bool(flags - {HIDDEN, ROLE}) or {HIDDEN, ROLE} <= flags


def ingest(journal: Journal, *, source: str, content: str, channel: str) -> dict:
    """Retain one external item as inert evidence. Never a command, never authority."""
    if not isinstance(content, str):
        raise ValueError("external content must be text")
    digest = hashlib.sha256(content.encode()).hexdigest()
    for retained in reversed(journal.replay("external.ingested")):
        # A redelivered item is not a new observation: return the retained fact
        # (first-seen time) instead of re-recording it with a new timestamp,
        # which the journal would refuse as an identity collision.
        if retained.payload.get("source") == source[:500] and retained.payload.get("content_sha256") == digest:
            return retained.payload
    flags = instruction_shaped(content)
    record = {"source": source[:500], "channel": channel[:100],
              "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
              "content": content[:MAX_RETAINED], "truncated": len(content) > MAX_RETAINED,
              "trust": "untrusted", "instruction_flags": flags, "quarantined": quarantines(flags),
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
    """Clustering key: NFKC, case-folded, punctuation and spacing collapsed, in every script (an ASCII-only key
    merged all non-Latin text into one cluster). Combining marks are part of words (Devanagari and Thai vowel
    and tone signs distinguish claims); NFKC runs again after case-folding so a folded dotted capital I
    recombines. Text with no word characters keys on itself."""
    folded = unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", text).casefold()).replace("i\u0307", "i")
    words = "".join(ch if ch.isalnum() or unicodedata.category(ch)[0] == "M" else " " for ch in folded)
    words = " ".join(words.split())
    return words or folded.strip()


def community_evidence(journal: Journal, channel: str, *, campaign_sources: int = 3) -> dict:
    """Typed, manipulation-resistant community evidence with preserved minority reports. Never authority.

    * one source carries one unit of weight per claim, whatever its volume (brigading by repetition fails);
    * identical normalised text from ``campaign_sources`` or more sources is flagged as a possible
      coordinated campaign and its cluster counts as ``campaign_sources - 1`` units (an integer of at
      least 2 is required, so a flag always means several identities): no more than an
      unflagged cluster can reach (sybils gain nothing over two identities), and never less (more
      independent agreement can never lower a claim's support or demote it to a minority report);
    * per kind, every distinct claim is kept with its support; claims below the most-supported one are the
      minority reports, listed explicitly;
    * classification is a keyword heuristic, labelled as such.
    """
    if type(campaign_sources) is not int or campaign_sources < 2:
        raise ValueError("campaign_sources is an integer of at least 2: one identity is never a campaign")
    items = [e.payload for e in journal.replay("external.ingested")
             if e.payload["channel"] == channel and not e.payload["quarantined"]]
    clusters: dict[str, dict] = {}
    for item in items:
        normal = _normal(item["content"])
        key = hashlib.sha256(normal.encode()).hexdigest()
        c = clusters.setdefault(key, {"text": item["content"][:500], "sources": set(), "first_at": item["at"],
                                      "kinds": set()})
        c["sources"].add(item["source"])
        # classify the normalised text (fancy Unicode must not hide a keyword) and take the union over the
        # cluster, so no single source's spelling or arrival order decides the cluster's kind
        c["kinds"] |= {k for k, rx in _KINDS.items() if rx.search(normal) or rx.search(item["content"])}
    by_kind: dict[str, list] = {k: [] for k in SIGNAL_KINDS}
    flagged = []
    for key, c in sorted(clusters.items()):
        campaign = len(c["sources"]) >= campaign_sources
        weight = min(len(c["sources"]), max(1, campaign_sources - 1))
        if campaign:
            flagged.append({"claim": c["text"][:200], "sources": len(c["sources"]),
                            "flag": "COORDINATED_CAMPAIGN_SUSPECTED", "counted_as": weight})
        record = {"claim": c["text"], "support_sources": weight, "raw_sources": len(c["sources"]),
                  "first_at": c["first_at"], "cluster": key[:16], "campaign_suspected": campaign}
        for kind in sorted(c["kinds"]) or ["unclassified"]:
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
