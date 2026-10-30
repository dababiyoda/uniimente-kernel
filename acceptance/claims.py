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
* ``LABEL_CROSSWALK``: two labels in use outside those vocabularies (LIVE, FOUNDER-DEVICE).

``CEILINGS`` is the one table of evidence kinds: each kind, the highest rung it can establish on that ladder and in
``greg.metrics`` terms, and the rule each ceiling comes from.

What is read: ``SCAN`` (evidence JSON under docs/ and tests/evidence/, acceptance/*.json, greg/path.json,
foundry/completion.yaml; never a schema). A claim is a string under a key in ``CLAIM_FIELDS``; its level is the
strongest ladder label it asserts. A label named under a negation ("not FOUNDER-USED", "may not be labelled
LIVE-BOUNDED", "FOUNDER-USED: pending") is not asserted. The reader is lexical: it reads labels, not prose, and its
limits are stated in ``_negated``.

What fails (``scan``):

0. a crosswalk that is not total and monotone onto the ladder (``crosswalk_problems``);
1. a record that declares ``evidence_kind`` names a kind in ``CEILINGS`` and claims no more than its ceiling; a kind
   beyond what tests establish (``acceptance.BEYOND_TESTS``) also names the record it rests on (``evidence_ref``), and
   its claim may not itself describe a container, rehearsal, test-key or fixture run;
2. a record that declares no kind claims no more than tests can establish (``acceptance.TEST_TIERS[-1]``,
   BODY_VERIFIED): a founder-used, live, founder-device or externally verified label needs a declared kind that can
   establish it.

A violation in a file another change owns is not edited here: it goes in ``ALLOWLIST`` with a reason and an owner,
and is still reported. An allowlist entry that no longer matches a violation fails, so none is silent or stale.

It reads files and prints. It writes, grants, blocks and authorizes nothing.

    python -m acceptance.claims            # JSON report; exit 1 on a violation or a stale allowlist entry
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import yaml

from acceptance import BEYOND_TESTS, LADDER, TEST_TIERS, rank
from greg import metrics
from greg.mission_control import REALITY

ROOT = Path(__file__).resolve().parents[1]
DIRECTIVE = ROOT / "docs" / "intent" / "sources" / "OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"


def directive_levels(path: Path = DIRECTIVE) -> tuple[str, ...]:
    """The section-56 levels, in the directive's order, read from its verbatim source."""
    lines = [line.strip() for line in Path(path).read_text().splitlines()]
    start = lines.index("56. REALITY LADDER")
    begin = lines.index("Use levels such as:", start)
    end = lines.index("Do not collapse these.", begin)
    return tuple(line for line in lines[begin + 1:end] if line)


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
LABEL_CROSSWALK = {"LIVE": "AUTHORIZED_LIVE", "FOUNDER-DEVICE": "FOUNDER_ACCEPTED"}
FOUNDER_DEVICE_PHRASE = re.compile(r"\bon (?:the )?(?:founder|alfonso)['’]?s (?:own |designated )?"
                                   r"(?:device|chromebook|hardware|machine)\b", re.I)

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
                                    "attestation, on the founder-designated body"},
    "external_verification": {"ladder": "EXTERNALLY_VERIFIED", "metrics": metrics.FOUNDER_TIER,
                              "basis": "acceptance.BEYOND_TESTS: an external observation that no test produces; "
                                       "greg.metrics says neither of its levels is an external verification"},
}
TEST_CEILING = TEST_TIERS[-1]                       # what a claim that declares no evidence kind may reach

CLAIM_FIELDS = ("reality", "reality_level", "reality_status", "current_reality", "acceptance_reality",
                "evidence_level", "evidence_tier", "declared_tier", "attained_tier", "tier", "status")
KIND_FIELD, REF_FIELD = "evidence_kind", "evidence_ref"
SCAN = ("docs/**/*.json", "docs/**/*.yaml", "docs/**/*.yml", "tests/evidence/**/*.json", "acceptance/*.json",
        "greg/path.json", "foundry/completion.yaml")

# Violations in files another open change owns: reported, never silent, never edited here.
# {(relative path, JSON pointer, label): {"reason": ..., "owner": ...}}
ALLOWLIST: dict = {}


def crosswalk_problems(levels: tuple | None = None, crosswalks: dict | None = None) -> list[str]:
    """Why the crosswalk is not total and monotone onto acceptance.LADDER; [] when it is.

    Total: every directive section-56 level, every greg.mission_control.REALITY label and every greg.metrics level
    maps to a rung of the ladder. Monotone: a stronger label in its own vocabulary's order never maps to a lower rung.
    A ceiling names a rung of the ladder and a greg.metrics level no stronger than that rung."""
    levels = directive_levels() if levels is None else levels
    crosswalks = {"directive section 56": (levels, DIRECTIVE_CROSSWALK), "greg.mission_control.REALITY":
                  (REALITY, REALITY_CROSSWALK), "greg.metrics": (METRICS_ORDER, METRICS_CROSSWALK)} \
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
                      LABEL_CROSSWALK):
        for label, rung in crosswalk.items():
            out.setdefault(label.replace("_", "-"), rung)
    out.pop("NONE")                                 # "none" in a claim claims nothing
    return out


LABELS = _labels()
PATTERNS = [(label, rung, _label_pattern(label)) for label, rung in LABELS.items()] + [
    ("on the founder's device", "FOUNDER_ACCEPTED", FOUNDER_DEVICE_PHRASE)]

REHEARSAL = re.compile(r"\brehears\w*|\btest[- ]keys?\b|\bper-test\b|--no-passphrase|\bthrowaway\b|"
                       r"\bsynthetic[- ](?:founder[- ])?authority\b|\bfixtures?\b", re.I)
CONTAINER = re.compile(r"\b(?:containers?|docker|sandbox(?:ed)?)\b", re.I)

CLAUSE_BREAK = re.compile(r"[;.()\[\]{}:!?]|\s[-–—]\s|\bbut\b|\bhowever\b", re.I)
NEGATORS = re.compile(r"\b(?:not|no|never|nothing|none|without|nor|neither|until|unless|pending|awaiting|requires?|"
                      r"omits?|omitted|lacks?|lacking|missing|absent|"
                      r"required|needs?|needed|cannot|can't|isn't|aren't|wasn't|beyond|below|above|short of|"
                      r"instead of|rather than|before|no longer)\b", re.I)
NEGATED_AFTER = re.compile(r"^[\s:,(\-–—]*(?:(?:is|are|was|were|remains?|stays?|still|yet|as|a)\s+)*"
                           r"(?:not\b|blocked|pending|unreached|unreachable|outstanding|deferred|required|needed|"
                           r"missing|absent|refused|forbidden|excluded|awaits|awaiting|requires|unmet|unproven|"
                           r"unverified|open\b)", re.I)
LABELLING = re.compile(r"\b(?:labell?ed|called|marked|reported as|described as|claimed as|presented as|counted as)\b", re.I)
FILLER = {"a", "an", "the", "be", "been", "being", "is", "are", "was", "were", "yet", "labelled", "labeled", "called",
          "marked", "reported", "claimed", "described", "shown", "treated", "counted", "as", "or", "and", "nor", "at",
          "any", "of", "on", "in", "to", "reach", "reached", "establish", "established", "even", "either", "own",
          "designated", "founder", "founder's", "founder’s", "alfonso's", "alfonso’s", "device", "tier", "level",
          "levels", "higher"}


def _only_filler(text: str) -> bool:
    for _label, _rung, pattern in PATTERNS:
        text = pattern.sub(" ", text)
    return all(word.lower() in FILLER for word in re.findall(r"[A-Za-z'’]+", text))


def _negated(text: str, start: int, end: int) -> bool:
    """Whether the label at [start, end) is named under a negation in its clause.

    Lexical, by declared rule. Clauses break at ; . ( ) [ ] : ! ?, a spaced dash, "but" and "however". The label is
    negated when, in its clause:

    * the nearest negator before it is followed only by filler words or other labels ("not FOUNDER-USED", "may not be
      labelled FOUNDER-USED, LIVE-BOUNDED or ...");
    * a negator before it governs a labelling verb that is followed only by filler or labels ("Nothing built in a
      container may be labelled FOUNDER-USED");
    * a negating word follows it ("FOUNDER-USED: pending").

    A negation written any other way reads as a claim, so the reader over-reports rather than hides: "not a container,
    FOUNDER-USED" is a claim. The second rule can hide one shape, a negator and a labelling verb in one clause that
    are unrelated ("is not a container run and is labelled FOUNDER-USED"); a claim field is a label, not that prose."""
    clause = max((m.end() for m in CLAUSE_BREAK.finditer(text, 0, start)), default=0)
    before = text[clause:start]
    negators = list(NEGATORS.finditer(before))
    if negators:
        if _only_filler(before[negators[-1].end():]):
            return True
        verbs = list(LABELLING.finditer(before, negators[0].end()))
        if verbs and _only_filler(before[verbs[-1].end():]):
            return True
    return bool(NEGATED_AFTER.match(text[end:end + 80]))


def asserted(value: str) -> list[tuple[str, str]]:
    """(label, rung) for every ladder label the text asserts, in order of appearance."""
    found = []
    for label, rung, pattern in PATTERNS:
        for match in pattern.finditer(value):
            if not _negated(value, match.start(), match.end()):
                found.append((match.start(), label, rung))
    return [(label, rung) for _start, label, rung in sorted(found)]


def _markers(text: str) -> list[str]:
    hits = []
    for pattern in (REHEARSAL, CONTAINER):
        hits += [m.group(0) for m in pattern.finditer(text) if not _negated(text, m.start(), m.end())]
    return hits


def check_record(record: dict, field: str) -> list[dict]:
    """The violations of one claim: ``record[field]`` against the evidence kind its record declares."""
    value = record.get(field)
    if not isinstance(value, str):
        return []
    claims = asserted(value)
    if not claims:
        return []
    label, rung = max(claims, key=lambda c: rank(c[1]))
    kind = record.get(KIND_FIELD)
    out = {"field": field, "value": value[:240], "claimed": label, "rung": rung, "kind": kind}
    if kind is not None:
        if not isinstance(kind, str) or kind not in CEILINGS:
            return [{**out, "why": f"evidence_kind {kind!r} is not one of {sorted(CEILINGS)}"}]
        ceiling = CEILINGS[kind]["ladder"]
        problems = []
        if rank(rung) > rank(ceiling):
            problems.append(f"{kind} establishes at most {ceiling} ({CEILINGS[kind]['basis']}); {label} claims {rung}")
        if ceiling in BEYOND_TESTS:
            ref = record.get(REF_FIELD)
            if not (isinstance(ref, str) and ref.strip()):
                problems.append(f"a {kind} claim names the record it rests on ({REF_FIELD})")
            markers = _markers(value + "; " + (ref if isinstance(ref, str) else ""))   # "; " ends a clause
            if markers:
                problems.append(f"declared {kind}, but the claim describes a {', '.join(sorted(set(markers)))} run")
        return [{**out, "ceiling": ceiling, "why": why} for why in problems]
    if rank(rung) > rank(TEST_CEILING):
        siblings = "; ".join(v for v in record.values() if isinstance(v, str))
        markers = sorted(set(_markers(siblings)))
        what = f"a {', '.join(markers)} run labelled {label}" if markers else f"{label} ({rung})"
        return [{**out, "ceiling": TEST_CEILING,
                 "why": f"{what}: no declared evidence kind can establish it; without one a claim reaches at most "
                        f"{TEST_CEILING}, what tests establish (acceptance.TEST_TIERS)"}]
    return []


def _pointer(parts) -> str:
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def claims_in(data, parts=()) -> list[dict]:
    """Every claim and its violations in one parsed document, with JSON pointers."""
    found = []
    if isinstance(data, dict):
        for field in CLAIM_FIELDS:
            if isinstance(data.get(field), str):
                found.append({"pointer": _pointer((*parts, field)), "field": field,
                              "violations": check_record(data, field)})
        for key, value in data.items():
            found += claims_in(value, (*parts, key))
    elif isinstance(data, list):
        for i, value in enumerate(data):
            found += claims_in(value, (*parts, i))
    return found


def _files(root: Path) -> list[Path]:
    files = {p for pattern in SCAN for p in root.glob(pattern) if p.is_file() and not p.name.endswith(".schema.json")}
    return sorted(files)


def _load(path: Path):
    text = path.read_text()
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def scan(root: Path | str = ROOT, *, allowlist: dict | None = None) -> dict:
    """Every claim under ``SCAN`` checked against its evidence kind; the guard fails when ``failing`` is non-empty."""
    root = Path(root)
    allowlist = ALLOWLIST if allowlist is None else allowlist
    files, unreadable, claims, violations = _files(root), [], 0, []
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            data = _load(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            unreadable.append({"file": relative, "why": f"{type(exc).__name__}: {str(exc)[:160]}"})
            continue
        for claim in claims_in(data):
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
    return {"files": len(files), "claims": claims, "failing": ladder + failing + stale, "violations": failing,
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
