"""Reality-claim inflation guard: no machine-readable claim may sit above what its evidence kind can establish.

Directive 2026-10-28 section 56: "Every major status claim must identify its strongest truthful evidence level ...
Passing tests may prove software behavior. They do not prove whole-product operation." Founder correction of
2026-10-30 (INTENT-20261030-BUILD-BEFORE-DEVICE-RUN): "Nothing built in a container is labelled founder-used, live or
externally verified"; its failure evidence is "a container run reported as founder-used". This makes that failure
executable over the repository's machine-readable claims.

No new ladder. The one ordered ladder is the acceptance harness's (``acceptance.LADDER``: the directive section-35
statuses, the same vocabulary as ``foundry.completion.EVIDENCE_TIERS``). Every other label in use maps onto it:

* ``DIRECTIVE_CROSSWALK``: the directive's seventeen section-56 levels, read from the directive source itself
  (``directive_levels``), never retyped;
* ``REALITY_CROSSWALK``: ``greg.mission_control.REALITY``;
* ``METRICS_CROSSWALK``: the closure evidence levels of ``greg.metrics`` (NONE, STRUCTURAL_CANDIDATE, FOUNDER_TIER);
* ``OUTCOME_CROSSWALK``: the Outcome contract's ``validation_status``, read from contracts/outcome.schema.json
  (``outcome_levels``);
* ``LABEL_CROSSWALK``: two labels in use outside those vocabularies (LIVE, FOUNDER-DEVICE).

``CEILINGS`` is the one table of evidence kinds: each kind, the highest rung it can establish on that ladder and in
``greg.metrics`` terms, and the rule each ceiling comes from.

What is read: ``SCAN`` (JSON and YAML under docs/ and under any directory named evidence, JSON under acceptance/,
greg/path.json, foundry/completion.yaml; never a schema). A claim is a string under a key in ``CLAIM_FIELDS`` (any
case, camelCase split), or any string a list or record under such a key holds; its level is the strongest ladder
label it asserts. Text is read NFKC-normalised, with Unicode dashes and spaces as '-' and ' ' and zero-width
characters removed (``normalise``). A label named under a negation ("not FOUNDER-USED", "may not be labelled
LIVE-BOUNDED", "FOUNDER-USED: pending") is not asserted. The reader is lexical: it reads labels, not prose, and its
rules and limits are stated in ``_negation``.

What fails (``scan``):

0. a crosswalk that is not total and monotone onto the ladder (``crosswalk_problems``);
1. a record that declares ``evidence_kind`` names a kind in ``CEILINGS`` and claims no more than its ceiling; a kind
   beyond what tests establish (``acceptance.BEYOND_TESTS``) also names something checkable it rests on
   (``evidence_ref``: a ledger digest or an existing file of the repository, never a placeholder), and no string of
   its record describes a container, rehearsal, test-key, fixture or test run;
2. a record that declares no kind claims no more than tests can establish (``acceptance.TEST_TIERS[-1]``,
   BODY_VERIFIED): a founder-used, live, founder-device or externally verified label needs a declared kind that can
   establish it;
3. a scanned file that cannot be read: what cannot be read cannot be shown to stay within its evidence.

A declared kind is the record's own declaration. The guard cannot verify it: it checks only that the claim stays
under that kind's ceiling, that the reference points at something a reviewer can check and that the record does not
describe a run the kind excludes. Whether the referenced record proves the kind is a reviewer's question.

A violation in a file another change owns is not edited here: it goes in ``ALLOWLIST`` with a reason and an owner,
and is still reported. An allowlist entry that no longer matches a violation fails, so none is silent or stale.

It reads files and prints. It writes, grants, blocks and authorizes nothing.

    python -m acceptance.claims            # JSON report; exit 1 on a violation, an unreadable file, a broken
                                           # crosswalk or a stale allowlist entry
"""
from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path
import re
import sys
import unicodedata

import yaml

from acceptance import BEYOND_TESTS, LADDER, TEST_TIERS, rank
from greg import metrics
from greg.mission_control import REALITY

ROOT = Path(__file__).resolve().parents[1]
DIRECTIVE = ROOT / "docs" / "intent" / "sources" / "OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"
OUTCOME_SCHEMA = ROOT / "contracts" / "outcome.schema.json"


def directive_levels(path: Path = DIRECTIVE) -> tuple[str, ...]:
    """The section-56 levels, in the directive's order, read from its verbatim source."""
    lines = [line.strip() for line in Path(path).read_text().splitlines()]
    start = lines.index("56. REALITY LADDER")
    begin = lines.index("Use levels such as:", start)
    end = lines.index("Do not collapse these.", begin)
    return tuple(line for line in lines[begin + 1:end] if line)


# The Outcome contract's validation_status, weakest first; ``outcome_levels`` reads its enum from the schema.
OUTCOME_ORDER = ("self_reported", "internally_observed", "externally_verified")


def outcome_levels(path: Path = OUTCOME_SCHEMA) -> tuple[str, ...]:
    """contracts/outcome.schema.json's validation_status values, in OUTCOME_ORDER (any value it does not know last)."""
    values = json.loads(Path(path).read_text())["properties"]["validation_status"]["enum"]
    return tuple(sorted(values, key=lambda v: OUTCOME_ORDER.index(v) if v in OUTCOME_ORDER else len(OUTCOME_ORDER)))


# Each label -> the rung of acceptance.LADDER it claims. A label maps to the rung its own evidence rule sits at,
# never higher. PACKAGED .. REBOOT-VERIFIED are properties of a real body process (BODY_VERIFIED: tests can reach
# it, in a container); "REBOOT-VERIFIED on the founder's device" is the founder-device label below.
# PRODUCTION-AUTHORIZED has no rung of its own on the acceptance ladder, so it takes the top rung: no kind in
# CEILINGS establishes it, and the crosswalk stays monotone.
DIRECTIVE_CROSSWALK = {
    "ASPIRATIONAL": "INTENDED", "PROPOSED": "INTENDED", "DOCUMENTED": "DESIGNED", "IMPLEMENTED": "IMPLEMENTED",
    "UNIT-TESTED": "UNIT_VERIFIED", "INTEGRATION-TESTED": "SANDBOX_VERIFIED", "SANDBOXED": "SANDBOX_VERIFIED",
    "LOCAL-REAL": "BODY_VERIFIED", "PACKAGED": "BODY_VERIFIED", "INSTALLED": "BODY_VERIFIED",
    "PERSISTENT": "BODY_VERIFIED", "REBOOT-VERIFIED": "BODY_VERIFIED", "FOUNDER-USED": "FOUNDER_ACCEPTED",
    "LIVE-BOUNDED": "AUTHORIZED_LIVE", "EXTERNALLY-VERIFIED": "EXTERNALLY_VERIFIED",
    "COMMERCIALLY-VALIDATED": "COMMERCIAL_OUTCOME_VERIFIED", "PRODUCTION-AUTHORIZED": "COMMERCIAL_OUTCOME_VERIFIED",
}
REALITY_CROSSWALK = {
    "PROPOSED": "INTENDED", "SIMULATED": "SANDBOX_VERIFIED", "LOCAL-REAL": "BODY_VERIFIED",
    "EXPERIMENTALLY-VERIFIED": "BODY_VERIFIED", "FOUNDER-DEVICE-VERIFIED": "FOUNDER_ACCEPTED",
    "EXTERNALLY-VERIFIED": "EXTERNALLY_VERIFIED",
}
METRICS_ORDER = ("NONE", metrics.STRUCTURAL_CANDIDATE, metrics.FOUNDER_TIER)
# A structural candidate is reachable in-process with a test key (tests/unit/test_path_build_frontier.py); the founder
# tier is the founder's own signed closure.
METRICS_CROSSWALK = {"NONE": "INTENDED", metrics.STRUCTURAL_CANDIDATE: "SANDBOX_VERIFIED",
                     metrics.FOUNDER_TIER: "FOUNDER_ACCEPTED"}
# contracts/outcome.schema.json: an outcome its producer reports about itself claims nothing verified; one the Kernel
# observed itself is reachable by a real Body process in a test; an external verification is what no test produces.
OUTCOME_CROSSWALK = {"self_reported": "IMPLEMENTED", "internally_observed": "BODY_VERIFIED",
                     "externally_verified": "EXTERNALLY_VERIFIED"}
LABEL_CROSSWALK = {"LIVE": "AUTHORIZED_LIVE", "FOUNDER-DEVICE": "FOUNDER_ACCEPTED"}
FOUNDER_DEVICE_PHRASE = re.compile(r"\bon (?:the |a )?(?:founder|alfonso)(?:['’]s)? (?:(?:own|designated|real|personal|"
                                   r"first)\s+)*(?:device|chromebook|hardware|machine|laptop|computer|phone|iphone|"
                                   r"mac|macbook|pc|desktop|tablet)\b", re.I)

# The evidence kinds, the highest rung each can establish (acceptance.LADDER; the same rung in greg.metrics terms),
# and the rule each ceiling comes from.
CEILINGS = {
    "unit_test": {"ladder": "SANDBOX_VERIFIED", "metrics": metrics.STRUCTURAL_CANDIDATE,
                  "basis": "acceptance/README.md: an in-process Body with a test clock is SANDBOX_VERIFIED at most"},
    "integration_container": {"ladder": "BODY_VERIFIED", "metrics": metrics.STRUCTURAL_CANDIDATE,
                              "basis": "acceptance.TEST_TIERS: tests establish at most BODY_VERIFIED, which needs a "
                                       "real Body process; the container is not the founder's device"},
    "rehearsal_key": {"ladder": "BODY_VERIFIED", "metrics": metrics.STRUCTURAL_CANDIDATE,
                      "basis": "greg.metrics.NOT_FOUNDER_TIER: a test key, a fixture's key or a --no-passphrase "
                               "rehearsal never moves the founder's path (greg.path.BUILD_RULE)"},
    "founder_device_run": {"ladder": "FOUNDER_ACCEPTED", "metrics": metrics.FOUNDER_TIER,
                           "basis": "acceptance.BEYOND_TESTS: FOUNDER_ACCEPTED needs Alfonso's signed acceptance; "
                                    "greg.metrics.founder_tier: signed by the enrolled founder key after its custody "
                                    "attestation; greg.metrics.vepmc counts such a closure only on the body a "
                                    "founder-signed BODY_DESIGNATE named (its founder_body condition)"},
    "external_verification": {"ladder": "EXTERNALLY_VERIFIED", "metrics": metrics.FOUNDER_TIER,
                              "basis": "acceptance.BEYOND_TESTS: an external observation that no test produces; "
                                       "greg.metrics says neither of its levels is an external verification"},
}
TEST_CEILING = TEST_TIERS[-1]                       # what a claim that declares no evidence kind may reach

# Keys are matched after ``field_name`` (any case, camelCase split): "Reality" and "realityLevel" are claim fields.
CLAIM_FIELDS = ("reality", "reality_level", "reality_status", "reality_tier", "current_reality", "acceptance_reality",
                "evidence_level", "evidence_tier", "declared_tier", "attained_tier", "tier", "status",
                "validation_status")
KIND_FIELD, REF_FIELD = "evidence_kind", "evidence_ref"
SCAN = ("docs/**/*.json", "docs/**/*.yaml", "docs/**/*.yml", "**/evidence/**/*.json", "**/evidence/**/*.yaml",
        "**/evidence/**/*.yml", "acceptance/**/*.json", "greg/path.json", "foundry/completion.yaml")

# Violations in files another open change owns: reported, never silent, never edited here.
# {(relative path, JSON pointer, label): {"reason": ..., "owner": ...}}
ALLOWLIST: dict = {
    ("docs/cortex/examples/routing-memory-verified-success.json", "/outcome_provenance/validation_status",
     "EXTERNALLY-VERIFIED"): {
        "reason": "a generated example of contracts/outcome.schema.json (cortex/examples.py writes it; its own ref "
                  "reads 'example: schedule executed as proved'), not a record of any run; it declares no evidence "
                  "kind, so the guard reports it",
        "owner": "the Cortex lane: cortex/examples.py generates docs/cortex/examples/, so a fix is made there"},
}


def crosswalk_problems(levels: tuple | None = None, crosswalks: dict | None = None) -> list[str]:
    """Why the crosswalk is not total and monotone onto acceptance.LADDER; [] when it is.

    Total: every directive section-56 level, every greg.mission_control.REALITY label, every greg.metrics level and
    every validation_status of the Outcome contract maps to a rung of the ladder. Monotone: a stronger label in its own vocabulary's order never maps to a lower rung.
    A ceiling names a rung of the ladder and a greg.metrics level no stronger than that rung."""
    levels = directive_levels() if levels is None else levels
    crosswalks = {"directive section 56": (levels, DIRECTIVE_CROSSWALK), "greg.mission_control.REALITY":
                  (REALITY, REALITY_CROSSWALK), "greg.metrics": (METRICS_ORDER, METRICS_CROSSWALK),
                  "contracts/outcome.schema.json validation_status": (outcome_levels(), OUTCOME_CROSSWALK)} \
        if crosswalks is None else crosswalks
    problems = []
    for name, (order, crosswalk) in crosswalks.items():
        missing = [label for label in order if label not in crosswalk]
        extra = sorted(set(crosswalk) - set(order))
        if missing or extra:
            problems.append(f"{name}: not total (unmapped {missing}, unknown {extra})")
        rungs = [crosswalk[label] for label in order if label in crosswalk]
        off = [r for r in rungs if r not in LADDER]
        if off:
            problems.append(f"{name}: maps onto {off}, which are not rungs of acceptance.LADDER")
        elif any(rank(a) > rank(b) for a, b in zip(rungs, rungs[1:])):
            problems.append(f"{name}: not monotone: {list(zip(order, rungs))}")
    for kind, ceiling in CEILINGS.items():
        if ceiling["ladder"] not in LADDER:
            problems.append(f"ceiling {kind}: {ceiling['ladder']} is not a rung of acceptance.LADDER")
        elif rank(METRICS_CROSSWALK.get(ceiling["metrics"], "COMMERCIAL_OUTCOME_VERIFIED")) > rank(ceiling["ladder"]):
            problems.append(f"ceiling {kind}: greg.metrics {ceiling['metrics']} is above its rung {ceiling['ladder']}")
    return problems


def _label_pattern(label: str) -> re.Pattern:
    parts = re.split(r"[-_ ]", label)
    body = r"[-_ ]".join(map(re.escape, parts))
    # A compound label of a ladder vocabulary is read in any case ("externally verified"). A one-word label and the
    # informal LABEL_CROSSWALK tokens are read in capitals only: "LIVE", never "a live page"; "FOUNDER-DEVICE", never
    # "founder-device proof".
    any_case = len(parts) > 1 and label not in LABEL_CROSSWALK
    return re.compile(r"(?<![A-Za-z0-9_-])" + body + r"(?![A-Za-z0-9_-])", re.I if any_case else 0)


def _labels() -> dict:
    out = {}
    for crosswalk in (dict(zip(LADDER, LADDER)), DIRECTIVE_CROSSWALK, REALITY_CROSSWALK, METRICS_CROSSWALK,
                      OUTCOME_CROSSWALK, LABEL_CROSSWALK):
        for label, rung in crosswalk.items():
            out.setdefault(label.replace("_", "-").upper(), rung)      # one pattern per label, whatever its case
    out.pop("NONE")                                 # "none" in a claim claims nothing
    return out


LABELS = _labels()
PATTERNS = [(label, rung, _label_pattern(label)) for label, rung in LABELS.items()] + [
    ("on the founder's device", "FOUNDER_ACCEPTED", FOUNDER_DEVICE_PHRASE)]

REHEARSAL = re.compile(r"\brehears\w*|\btest[- ]keys?\b|\bper-test\b|--no-passphrase|\bthrowaway\b|"
                       r"\bsynthetic[- ](?:founder[- ])?authority\b|\bfixtures?\b", re.I)
CONTAINER = re.compile(r"\b(?:containers?|docker|sandbox(?:ed)?)\b", re.I)
# A run of the test machinery itself: what a test, a CI job or a simulation produces is never a founder-device run or
# an external verification. "CI" is read in capitals only.
TEST_RUN = re.compile(r"\bpytest\b|\bgithub actions\b|\bubuntu-latest\b|\bcontinuous integration\b|"
                      r"\btest (?:runs?|suites?|harness)\b|\b(?:unit|integration)[- ]tests?\b|\bsimulat(?:ed|ion|or)\b|"
                      r"\bmock(?:ed|s)?\b|\bstub(?:bed|s)?\b|\bdry[- ]run\b", re.I)
CI = re.compile(r"(?<![A-Za-z0-9_-])CI(?![A-Za-z0-9_-])")
MARKERS = (REHEARSAL, CONTAINER, TEST_RUN, CI)

CLAUSE_BREAK = re.compile(r"[;.()\[\]{}:!?]|\s[-–—]\s|\bbut\b|\bhowever\b", re.I)
NEGATORS = re.compile(r"\b(?:not|no|never|nothing|none|without|nor|neither|until|unless|pending|awaiting|requires?|"
                      r"omits?|omitted|lacks?|lacking|missing|absent|"
                      r"required|needs?|needed|cannot|can't|isn't|aren't|wasn't|beyond|below|above|short of|"
                      r"instead of|rather than|before|no longer)\b", re.I)
# After a label, only a status that says the label itself is unmet, right after it or after one colon:
# "FOUNDER-USED: pending", "LIVE-BOUNDED is not yet reached". Never after a comma or a dash, never "not" followed by
# anything else ("FOUNDER-USED, not a container run" and "FOUNDER-USED: not simulated" claim FOUNDER-USED), never
# "as required" or "open".
NEGATED_AFTER = re.compile(r"^ *:? *(?:(?:is|are|was|were|remains?|stays?|still)\s+)*"
                           r"(?:not\s+yet\b|not\s+(?:reached|attained|established|achieved|met|claimed)\b|pending\b|"
                           r"blocked\b|unreached\b|unreachable\b|deferred\b|unmet\b|unproven\b|unverified\b|"
                           r"unattained\b|awaiting\b|awaits\b|refused\b|forbidden\b|excluded\b)", re.I)
LABELLING = re.compile(r"\b(?:labell?ed|called|marked|reported as|described as|claimed as|presented as|counted as)\b", re.I)
# Between a negator and the labelling verb it governs: a comma or a conjunction starts another statement
# ("never failed and labelled FOUNDER-USED" claims FOUNDER-USED).
COORDINATION = re.compile(r",|\b(?:and|then|so|also|plus|while|whereas|after|once|because|since|thus|hence)\b", re.I)
FILLER = {"a", "an", "the", "be", "been", "being", "is", "are", "was", "were", "yet", "labelled", "labeled", "called",
          "marked", "reported", "claimed", "described", "shown", "treated", "counted", "as", "or", "and", "nor", "at",
          "any", "of", "on", "in", "to", "reach", "reached", "establish", "established", "even", "either", "own",
          "designated", "founder", "founder's", "founder’s", "alfonso's", "alfonso’s", "device", "tier", "level",
          "levels", "higher", "run", "ran", "built", "executed"}
DASHES = re.compile(r"[‐-―−⸺⸻﹘﹣]")


def normalise(text: str) -> str:
    """The text a label is read in: NFKC, Unicode dashes as '-', every space as ' ', format characters (zero-width
    spaces and joiners, the soft hyphen, the byte-order mark) removed. "FOUNDER‐USED" with U+2010 is FOUNDER-USED."""
    text = "".join(ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf")
    return re.sub(r"\s", " ", DASHES.sub("-", text))


CAMEL, SEPARATORS = re.compile(r"(?<=[a-z0-9])(?=[A-Z])"), re.compile(r"[-\s]+")


@functools.lru_cache(maxsize=65536)
def field_name(key) -> str:
    """The claim field a key names: camelCase split, any case, '-' or spaces as '_' ("realityLevel" is reality_level)."""
    return SEPARATORS.sub("_", CAMEL.sub("_", str(key))).lower()


def _only_filler(text: str) -> bool:
    for _label, _rung, pattern in PATTERNS:
        text = pattern.sub(" ", text)
    return all(word.lower() in FILLER for word in re.findall(r"[A-Za-z'’]+", text))


def _negation(text: str, start: int, end: int) -> str | None:
    """Which rule names the label at [start, end) under a negation in its clause; None when none does.

    Lexical, by declared rule. Clauses break at ; . ( ) [ ] : ! ?, a spaced dash, "but" and "however". The label is
    negated when, in its clause:

    * "before": the nearest negator before it is followed only by filler words or other labels ("not FOUNDER-USED",
      "may not be labelled FOUNDER-USED, LIVE-BOUNDED or ...");
    * "verb": a negator before it governs a labelling verb that is followed only by filler or labels, with no comma or
      conjunction between the two ("Nothing built in a container may be labelled FOUNDER-USED"; "never failed and
      labelled FOUNDER-USED" is a claim);
    * "after": a status that says the label itself is unmet follows it directly or after one colon
      (``NEGATED_AFTER``: "FOUNDER-USED: pending"). This is the weakest rule: ``asserted`` drops it when the record
      describes a container, rehearsal or test run.

    A negation written any other way reads as a claim, so the reader over-reports: "not a container, FOUNDER-USED",
    "FOUNDER-USED, not a container run" and "FOUNDER-USED (not a container run)" are claims. It is still a reader of
    words, not of meaning, and can be phrased around: a sentence whose negator and labelling verb are unrelated but
    joined without a comma or conjunction ("is not a container run labelled FOUNDER-USED") hides the label. The guard
    stops mislabelled records; it does not replace reading them."""
    clause = max((m.end() for m in CLAUSE_BREAK.finditer(text, 0, start)), default=0)
    before = text[clause:start]
    negators = list(NEGATORS.finditer(before))
    if negators:
        if _only_filler(before[negators[-1].end():]):
            return "before"
        verbs = list(LABELLING.finditer(before, negators[0].end()))
        if verbs and _only_filler(before[verbs[-1].end():]) and any(
                not COORDINATION.search(before[n.end():verbs[-1].start()]) for n in negators
                if n.end() <= verbs[-1].start()):
            return "verb"
    return "after" if NEGATED_AFTER.match(text[end:end + 80]) else None


def _negated(text: str, start: int, end: int) -> bool:
    return _negation(text, start, end) is not None


def asserted(value: str, *, after_holds: bool = True) -> list[tuple[str, str]]:
    """(label, rung) for every ladder label the text asserts, in order of appearance. With ``after_holds`` False a
    label negated only by a status after it ("FOUNDER-USED: pending") counts as asserted. An informal label read in
    capitals inside text ("LIVE", never "a live page") is read in any case when it is the whole value."""
    value = normalise(value)
    whole = value.strip().upper()
    if whole in LABEL_CROSSWALK:                    # a value that is only "live" or "Live" is the LIVE label
        return [(whole, LABEL_CROSSWALK[whole])]
    found = []
    for label, rung, pattern in PATTERNS:
        for match in pattern.finditer(value):
            negation = _negation(value, match.start(), match.end())
            if negation is None or (negation == "after" and not after_holds):
                found.append((match.start(), label, rung))
    return [(label, rung) for _start, label, rung in sorted(found)]


def _markers(text: str) -> list[str]:
    """The container, rehearsal, test-key, fixture and test-run words the text does not negate."""
    text = normalise(text)
    hits = []
    for pattern in MARKERS:
        hits += [m.group(0) for m in pattern.finditer(text) if not _negated(text, m.start(), m.end())]
    return hits


def _strings(value) -> list[str]:
    """Every string a record holds, at any depth."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _strings(v)]
    return []


def _get(record: dict, field: str):
    return next((value for key, value in record.items() if field_name(key) == field), None)


DIGEST = re.compile(r"\bsha256:[0-9a-f]{64}\b")
PLACEHOLDER = re.compile(r"^(?:none|n/?a|tbd|tba|todo|pending|unknown|null|nil|x+|-+|\?+|see (?:above|below)|later)$",
                         re.I)


def ref_problem(ref, root: Path | None = None, relative: str | None = None) -> str | None:
    """Why ``evidence_ref`` names nothing a reviewer can check; None when it names a ledger digest (sha256: and 64 hex
    digits, never all zeros) or an existing file of the repository other than the record's own."""
    if not isinstance(ref, str) or not ref.strip():
        return f"names nothing it rests on ({REF_FIELD} is missing or empty)"
    text = normalise(ref).strip()
    if PLACEHOLDER.match(text):
        return f"{REF_FIELD} {text!r} is a placeholder, not a record"
    if any(set(d[7:]) != {"0"} for d in DIGEST.findall(text)):
        return None
    target = text.split("#", 1)[0].strip()
    if root is not None and target and not Path(target).is_absolute() and ".." not in Path(target).parts \
            and target != relative and (Path(root) / target).is_file():
        return None
    return (f"{REF_FIELD} {text[:80]!r} is neither a ledger digest (sha256: and 64 hex digits) nor an existing file "
            "of this repository")


def check_record(record: dict, field: str, value=None, *, root: Path | None = None,
                 relative: str | None = None) -> list[dict]:
    """The violations of one claim: ``value`` (default ``record[field]``) against the evidence kind its record
    declares. ``root`` and ``relative`` let an ``evidence_ref`` resolve to a file of the scanned tree."""
    value = _get(record, field) if value is None else value
    if not isinstance(value, str):
        return []
    others = [s for key, v in record.items() if field_name(key) != KIND_FIELD for s in _strings(v)]
    markers = sorted(set(_markers("; ".join(others))))                     # "; " ends a clause
    claims = asserted(value, after_holds=not markers)
    if not claims:
        return []
    label, rung = max(claims, key=lambda c: rank(c[1]))
    kind = _get(record, KIND_FIELD)
    out = {"field": field, "value": normalise(value)[:240], "claimed": label, "rung": rung, "kind": kind}
    if kind is not None:
        if not isinstance(kind, str) or kind not in CEILINGS:
            return [{**out, "why": f"evidence_kind {kind!r} is not one of {sorted(CEILINGS)}"}]
        ceiling = CEILINGS[kind]["ladder"]
        problems = []
        if rank(rung) > rank(ceiling):
            problems.append(f"{kind} establishes at most {ceiling} ({CEILINGS[kind]['basis']}); {label} claims {rung}")
        if ceiling in BEYOND_TESTS:
            unchecked = ref_problem(_get(record, REF_FIELD), root, relative)
            if unchecked:
                problems.append(f"a {kind} claim names a record a reviewer can check: {unchecked}")
            if markers:
                problems.append(f"declared {kind}, but the record describes a {', '.join(markers)} run")
        return [{**out, "ceiling": ceiling, "why": why} for why in problems]
    if rank(rung) > rank(TEST_CEILING):
        what = f"a {', '.join(markers)} run labelled {label}" if markers else f"{label} ({rung})"
        return [{**out, "ceiling": TEST_CEILING,
                 "why": f"{what}: no declared evidence kind can establish it; without one a claim reaches at most "
                        f"{TEST_CEILING}, what tests establish (acceptance.TEST_TIERS)"}]
    return []


def _pointer(parts) -> str:
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _held(value, parts) -> list[tuple[tuple, str]]:
    """(pointer parts, string) for every string a claim field holds: itself, the items of a list, the fields of a
    record, at any depth."""
    if isinstance(value, str):
        return [(parts, value)]
    if isinstance(value, dict):
        return [found for key, v in value.items() for found in _held(v, (*parts, key))]
    if isinstance(value, (list, tuple)):
        return [found for i, v in enumerate(value) for found in _held(v, (*parts, i))]
    return []


def claims_in(data, parts=(), *, root: Path | None = None, relative: str | None = None, _seen=None) -> list[dict]:
    """Every claim and its violations in one parsed document, with JSON pointers. A string under a claim field is a
    claim of the record holding the field; a record under a claim field adds its own fields (an evidence kind, say)
    to that record's. Each string is read once."""
    seen = set() if _seen is None else _seen
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            field = field_name(key)
            if field not in CLAIM_FIELDS:
                continue
            record = {**data, **value} if isinstance(value, dict) else data
            for where, text in _held(value, (*parts, key)):
                pointer = _pointer(where)
                if pointer not in seen:
                    seen.add(pointer)
                    found.append({"pointer": pointer, "field": field, "violations": check_record(
                        record, field, text, root=root, relative=relative)})
        for key, value in data.items():
            found += claims_in(value, (*parts, key), root=root, relative=relative, _seen=seen)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            found += claims_in(value, (*parts, i), root=root, relative=relative, _seen=seen)
    return found


def _files(root: Path) -> list[Path]:
    files = {p for pattern in SCAN for p in root.glob(pattern)
             if p.is_file() and ".git" not in p.relative_to(root).parts and not p.name.endswith(".schema.json")}
    return sorted(files)


def _load(path: Path):
    """One parsed document; a YAML file of several documents is their list. A byte-order mark is read past."""
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".json":
        return json.loads(text)
    documents = list(yaml.safe_load_all(text))
    return documents[0] if len(documents) == 1 else documents


def scan(root: Path | str = ROOT, *, allowlist: dict | None = None) -> dict:
    """Every claim under ``SCAN`` checked against its evidence kind; the guard fails when ``failing`` is non-empty.
    ``ALLOWLIST`` names files of this repository, so it applies only when ``root`` is this checkout."""
    root = Path(root)
    if allowlist is None:
        allowlist = ALLOWLIST if root.resolve() == ROOT else {}
    files, unreadable, claims, violations = _files(root), [], 0, []
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            data = _load(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            unreadable.append({"file": relative, "why": f"unreadable, so no claim in it can be checked: "
                                                        f"{type(exc).__name__}: {str(exc)[:160]}"})
            continue
        for claim in claims_in(data, root=root, relative=relative):
            claims += 1
            violations += [{"file": relative, "pointer": claim["pointer"], **v} for v in claim["violations"]]
    failing, allowed, matched = [], [], set()
    for v in violations:
        key = (v["file"], v["pointer"], v["claimed"])
        entry = allowlist.get(key)
        if entry and str(entry.get("reason", "")).strip() and str(entry.get("owner", "")).strip():
            allowed.append({**v, "allowlisted": entry})
            matched.add(key)
        else:
            failing.append(v)
    stale = [{"entry": list(key), "why": "matches no violation: remove it"} for key in allowlist if key not in matched]
    ladder = [{"crosswalk": problem} for problem in crosswalk_problems()]
    return {"files": len(files), "claims": claims, "failing": ladder + failing + stale + unreadable,
            "violations": failing,
            "crosswalk_problems": ladder,
            "allowlisted": allowed, "stale_allowlist": stale, "unreadable": unreadable,
            "ceilings": CEILINGS, "test_ceiling": TEST_CEILING,
            "rule": "a claim may not exceed what its declared evidence kind can establish; without a declared kind, "
                    "what tests establish",
            "acts": "reads files only; writes, grants and blocks nothing"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m acceptance.claims", description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(ROOT), help="repository to read (default: this checkout)")
    args = parser.parse_args(argv)
    report = scan(args.root)
    print(json.dumps(report, indent=1, default=str))
    print(f"{'FAIL' if report['failing'] else 'PASS'}: {report['claims']} claims in {report['files']} files; "
          f"{len(report['crosswalk_problems'])} crosswalk problem(s), "
          f"{len(report['violations'])} violation(s), {len(report['allowlisted'])} allowlisted, "
          f"{len(report['stale_allowlist'])} stale allowlist entr(ies), {len(report['unreadable'])} unreadable",
          file=sys.stderr)
    return 1 if report["failing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
