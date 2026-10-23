"""Claim/span binding, declared quality, freshness and contradictions in a bounded corpus.

A claim that restates its supporting spans in other words is also checked against them. The check is a conservative
refuter of six kinds of change that alter what a restatement says: figures, negation, certainty, scope, direction and
named terms. Finding none is not entailment; a flag can be a legitimate rewording, and is reported for review.
"""
from datetime import datetime, timezone
import re

from .contracts import CognitionError, digest

CHANGE_CLASSES = ("figure", "negation", "certainty", "scope", "direction", "named_term")
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
NEGATORS = frozenset({"not", "no", "never", "none", "nor", "neither", "without", "nobody", "nothing", "cannot"})
HEDGES = frozenset({"may", "might", "could", "possibly", "perhaps", "likely", "probably", "suggests", "suggest",
                    "suggested", "appears", "appear", "preliminary", "estimated", "approximately", "roughly"})
STRONG = frozenset({"will", "proves", "proved", "proven", "prove", "certainly", "definitely", "guarantees",
                    "guaranteed", "confirms", "confirmed", "undoubtedly"})
UNIVERSAL = frozenset({"all", "every", "everyone", "everything", "always", "never", "none", "nobody", "entire",
                       "entirely", "completely", "each"})
UP = frozenset({"increase", "increased", "increases", "increasing", "rise", "rises", "rose", "risen", "rising", "grew",
                "grow", "grows", "grown", "growing", "higher", "gain", "gained", "gains", "raise", "raised", "raises",
                "boost", "boosted", "boosts"})
DOWN = frozenset({"decrease", "decreased", "decreases", "decreasing", "fall", "falls", "fell", "fallen", "falling",
                  "decline", "declined", "declines", "drop", "dropped", "drops", "lower", "lowered", "lowers", "reduce",
                  "reduced", "reduces", "reducing", "cut", "cuts", "fewer", "shrank", "shrink", "shrinks"})


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


_IMPLICIT_NEGATION = re.compile(r"\b(?:fail(?:s|ed)?|unable) to\b", re.I)
# Words that open sentences without naming anything; any other capitalised opening word is checked as a name.
_OPENERS = frozenset({"the", "a", "an", "this", "that", "these", "those", "it", "its", "they", "their", "we", "our",
                      "he", "she", "his", "her", "in", "on", "at", "for", "of", "and", "but", "or", "as", "by", "with",
                      "from", "to", "after", "before", "during", "since", "while", "when", "where", "if", "each",
                      "every", "all", "some", "most", "many", "no", "not", "more", "fewer", "less", "one", "two",
                      "three", "there", "here", "both", "only", "about", "over", "under"})


def _negated(words, text: str = "") -> bool:
    return any(w in NEGATORS or w.endswith("n't") for w in words) or bool(_IMPLICIT_NEGATION.search(text))


# Spelled-out cardinals from two up are figures too ("one" is too often not a number to read as one).
_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                     "fourteen fifteen sixteen seventeen eighteen nineteen".split()) if i >= 2}
_TENS = {w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)}
_SPELLED = re.compile(r"\b(?:(%s)(?:[- ](%s))?|(%s))\b" % ("|".join(_TENS), "|".join(_UNITS), "|".join(_UNITS)), re.I)
NUMBER_WORDS = frozenset(_UNITS) | frozenset(_TENS)


def _spelled(match) -> str:
    tens, unit, alone = (g.lower() if g else None for g in match.groups())
    return str(_TENS[tens] + (_UNITS.get(unit, 0)) if tens else _UNITS[alone])


def _figures(text: str) -> set[str]:
    text = _SPELLED.sub(_spelled, text)
    text = re.sub(r"(\d)\s*(?:percent|per cent)\b", r"\1%", text, flags=re.I)
    return {f.replace(",", "").rstrip(".") for f in _FIGURE.findall(text)}


def _directions(words) -> set[str]:
    return ({"up"} if UP.intersection(words) else set()) | ({"down"} if DOWN.intersection(words) else set())


def _named_terms(text: str) -> set[str]:
    """Capitalised words that do not open a sentence: names, organisations, products, places."""
    terms = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        words = _WORD.findall(sentence)
        for i, word in enumerate(words):
            if word[0].isupper() and word.lower() not in NUMBER_WORDS and (i or word.lower() not in _OPENERS):
                terms.add(word)
    return terms


def distortions(claim: str, support: list[str]) -> list[dict]:
    """The ways a claim changes what its supporting spans say, by class; [] when none of the six is detected."""
    joined = " ".join(support)
    cw, sw = _words(claim), _words(joined)
    found = []
    missing = sorted(_figures(claim) - _figures(joined))
    if missing:
        found.append({"class": "figure", "detail": f"figures not in the supporting spans: {missing}"})
    if _negated(cw, claim) != _negated(sw, joined):
        found.append({"class": "negation", "detail": "negation added" if _negated(cw, claim) else "negation removed"})
    hedged_claim, hedged_support = bool(HEDGES.intersection(cw)), bool(HEDGES.intersection(sw))
    stronger = sorted(set(cw) & STRONG - set(sw))
    if (hedged_support and not hedged_claim) or stronger:
        found.append({"class": "certainty", "detail": (f"stronger certainty than the spans: {stronger}" if stronger
                                                       else "the spans are hedged; the claim is not")})
    wider = sorted(set(cw) & UNIVERSAL)
    if wider and not UNIVERSAL.intersection(sw):        # "each" for "all" keeps the scope; "all" for "some" widens it
        found.append({"class": "scope", "detail": f"universal scope the spans do not state: {wider}"})
    claimed, supported = _directions(cw), _directions(sw)
    if claimed and supported and claimed.isdisjoint(supported):
        found.append({"class": "direction", "detail": f"direction {sorted(claimed)} against the spans' {sorted(supported)}"})
    lowered = joined.lower()
    unnamed = sorted(t for t in _named_terms(claim) if t.lower() not in lowered)
    if unnamed:
        found.append({"class": "named_term", "detail": f"named terms not in the supporting spans: {unnamed}"})
    return found


def assess(data, geometry):
    from .solvers import result
    claim, sources, bindings = data["claim"], data["sources"], data["bindings"]
    if not isinstance(claim, str) or not claim or not 1 <= len(sources) <= 32 or not 1 <= len(bindings) <= 64:
        raise CognitionError("claim and bounded sources/bindings required")
    now = datetime.now(timezone.utc)
    index = {}
    limitations = ["span binding is not entailment, factual accuracy, causality or institutional acceptance",
                   "the restatement check refutes six kinds of change (figures, negation, certainty, scope, direction, "
                   "named terms); finding none is not entailment, and a flag may be a legitimate rewording"]
    for s in sources:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or s["id"] in index or not isinstance(s.get("text"), str):
            raise CognitionError("unique source IDs and text required")
        if s.get("digest") != digest(s["text"]):
            raise CognitionError("forged source digest")
        if not s.get("provenance") or s.get("quality") not in ("primary", "secondary", "unverified"):
            raise CognitionError("source provenance and declared quality required")
        expires = datetime.fromisoformat(s["expires_at"].replace("Z", "+00:00"))
        if expires.tzinfo is None or expires <= now:
            raise CognitionError("stale or undated evidence")
        index[s["id"]] = s
    contradictions = []
    for b in bindings:
        if b.get("source_id") not in index or not isinstance(b.get("quote"), str) or not b["quote"] or b["quote"] not in index[b["source_id"]]["text"]:
            raise CognitionError("evidence mismatch")
        if b.get("relationship") not in ("supports", "contradicts", "context"):
            raise CognitionError("unsupported evidence relationship")
        if b["relationship"] == "contradicts":
            contradictions.append(b)
    support = [b["quote"] for b in bindings if b["relationship"] == "supports"]
    changed = distortions(claim, support) if support else []
    missing = []
    if contradictions:
        missing.append("CONTRADICTION: retain dissent; request the next decisive observation")
    if not support:
        missing.append("INSUFFICIENT_EVIDENCE: no span is declared to support the claim")
    if changed:
        missing.append("DISTORTION: the claim changes what its supporting spans say ("
                       + ", ".join(c["class"] for c in changed) + "); restate it or bind a span that says it")
    return result({"claim": claim, "bound": True, "contested": bool(contradictions), "distortions": changed},
                  {"claim": claim, "sources": [{k:v for k,v in s.items() if k != "text"} for s in sources], "bindings": bindings, "contradictions": contradictions,
                   "distortions": changed, "change_classes_checked": list(CHANGE_CLASSES),
                   "limitations": limitations, "source_quality": "declared, not independently authenticated"},
                  status="ABSTAIN" if missing else "ANSWER", missing=tuple(missing))
