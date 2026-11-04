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
* ``SOP_CROSSWALK``: the reality labels of docs/PROJECT_COGNITION_SOP.md section 3 (``sop_levels``), which the PR
  and Discussion templates offer, MAC-VERIFIED among them;
* ``LABEL_CROSSWALK`` and ``DEVICE_CROSSWALK``: labels in use outside those vocabularies (LIVE, FOUNDER-DEVICE, and
  verified-on-a-device labels such as CHROMEBOOK-VERIFIED).

A label shared by two vocabularies maps to one rung. ``CEILINGS`` is the one table of evidence kinds: each kind, the
highest rung it can establish on that ladder, in ``greg.metrics`` terms and among the directive's section-56 levels
(which are not collapsed: a unit test establishes UNIT-TESTED, not INTEGRATION-TESTED), and the rule each ceiling
comes from.

What is read (``scanned``): JSON, JSON Lines and YAML, by extension in any case, under docs/, acceptance/ and any
directory named evidence, plus greg/path.json and foundry/completion.yaml. A JSON Schema is recognised by its
``$schema`` and read as one: its property names and its enum, const, default and example values are not claims. A
claim is a string under a key in ``CLAIM_FIELDS`` (any case, camelCase split), or any string a list or record under
such a key holds, read against its nearest enclosing record; its level is the strongest ladder label it asserts.
Text is read NFKC-normalised, with Unicode dashes and spaces as '-' and ' ' and zero-width characters removed
(``normalise``). A label named under a negation ("not FOUNDER-USED", "may not be labelled LIVE-BOUNDED",
"FOUNDER-USED: pending") is not asserted. The reader is lexical: it reads labels, not prose, and its rules and
limits are stated in ``_negation``.

What fails (``scan``):

0. a crosswalk that is not total and monotone onto the ladder (``crosswalk_problems``);
1. a record that declares ``evidence_kind`` names a kind in ``CEILINGS`` and claims no more than its ceiling; a kind
   beyond what tests establish (``acceptance.BEYOND_TESTS``) also names something checkable it rests on
   (``evidence_ref``: a ledger digest or an existing file of the repository, never a placeholder), and no string of
   its record describes a container, rehearsal, test-key, fixture or test run;
2. a record that declares no kind claims no more than tests can establish (``acceptance.TEST_TIERS[-1]``,
   BODY_VERIFIED): a founder-used, live, founder-device or externally verified label needs a declared kind that can
   establish it. When its claim or its statement of evidence (``EVIDENCE_FIELDS``) names a unit test, an integration
   test, a container or a rehearsal, it also claims no more than that kind's ceiling (``implied_kind``: "LOCAL-REAL"
   from unit tests fails, and so does "REBOOT-VERIFIED in a container");
3. a scanned file that cannot be read, nested too deep included: what cannot be read cannot be shown to stay within
   its evidence.

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
import os
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


SOP = ROOT / "docs" / "PROJECT_COGNITION_SOP.md"


def sop_levels(path: Path = SOP) -> tuple[str, ...]:
    """The reality labels of the cognition SOP's Context Reconstruction Packet ("### Current reality"), in its order."""
    lines = [line.strip() for line in Path(path).read_text().splitlines()]
    start = lines.index("### Current reality")
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("### "))
    return tuple(line[2:].rstrip(";.").strip() for line in lines[start + 1:end] if line.startswith("- "))


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
# The SOP's reality labels, which the PR and Discussion templates offer. Its list is not an order (PROPOSED and
# ASPIRATIONAL come last), so it is checked total, not monotone. TESTED claims what a passing test shows at least;
# MAC-VERIFIED is verified on the founder's Mac, the first body when the SOP was written
# (INTENT-2026-09-22-FIRST-BODY), never a container. BLOCKED is not a rung (acceptance.BLOCKED: it says why a rung
# cannot be reached), so it claims nothing.
SOP_CROSSWALK = {
    "IMPLEMENTED": "IMPLEMENTED", "INTEGRATED": "INTEGRATED", "TESTED": "UNIT_VERIFIED",
    "SANDBOXED": "SANDBOX_VERIFIED", "LOCAL-REAL": "BODY_VERIFIED", "MAC-VERIFIED": "FOUNDER_ACCEPTED",
    "PERSISTENT": "BODY_VERIFIED", "REBOOT-VERIFIED": "BODY_VERIFIED", "EXTERNALLY-VERIFIED": "EXTERNALLY_VERIFIED",
    "PRODUCTION-AUTHORIZED": "COMMERCIAL_OUTCOME_VERIFIED", "PROPOSED": "INTENDED", "ASPIRATIONAL": "INTENDED",
}
NOT_RUNGS = ("BLOCKED",)
LABEL_CROSSWALK = {"LIVE": "AUTHORIZED_LIVE", "FOUNDER-DEVICE": "FOUNDER_ACCEPTED"}
# Verified on a named device: the founder's device, which no container or test is (read in any case, and as one label
# when devices are listed with '/': "not MAC/Chromebook-verified").
DEVICES = ("MAC", "MACBOOK", "CHROMEBOOK", "DEVICE", "HARDWARE")
DEVICE_CROSSWALK = {f"{device}-VERIFIED": "FOUNDER_ACCEPTED" for device in DEVICES}
DEVICE_LIST = re.compile(r"(?<![A-Za-z0-9_-])(?:(?:%s) ?/ ?)+(?:%s)[-_ ]verified(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9_-])"
                         % (("|".join(DEVICES),) * 2), re.I)
FOUNDER_DEVICE_PHRASE = re.compile(r"\bon (?:the |a )?(?:founder|alfonso)(?:['’]s)? (?:(?:own|designated|real|personal|"
                                   r"first)\s+)*(?:device|chromebook|hardware|machine|laptop|computer|phone|iphone|"
                                   r"mac|macbook|pc|desktop|tablet)\b", re.I)

# The evidence kinds, the highest rung each can establish (acceptance.LADDER; the same rung in greg.metrics terms;
# the highest of the directive's section-56 levels, which are not collapsed), and the rule each ceiling comes from.
CEILINGS = {
    "unit_test": {"ladder": "SANDBOX_VERIFIED", "metrics": metrics.STRUCTURAL_CANDIDATE, "directive": "UNIT-TESTED",
                  "basis": "acceptance/README.md: an in-process Body with a test clock is SANDBOX_VERIFIED at most; "
                           "among section 56's levels a unit test is UNIT-TESTED, below INTEGRATION-TESTED and "
                           "SANDBOXED"},
    "integration_container": {"ladder": "BODY_VERIFIED", "metrics": metrics.STRUCTURAL_CANDIDATE,
                              "directive": "PERSISTENT",
                              "basis": "acceptance.TEST_TIERS: tests establish at most BODY_VERIFIED, which needs a "
                                       "real Body process; the container is not the founder's device, and it cannot "
                                       "reboot its host (docs/collaboration/GREG-PRODUCT-CONVERGENCE-2026-09-26.md: "
                                       "'REBOOT-VERIFIED is not claimed: power loss was simulated'), so it reaches "
                                       "PERSISTENT, not REBOOT-VERIFIED"},
    "rehearsal_key": {"ladder": "BODY_VERIFIED", "metrics": metrics.STRUCTURAL_CANDIDATE, "directive": "PERSISTENT",
                      "basis": "greg.metrics.NOT_FOUNDER_TIER: a test key, a fixture's key or a --no-passphrase "
                               "rehearsal never moves the founder's path (greg.path.BUILD_RULE); a rehearsal installs "
                               "and runs GREG in its container, which reaches PERSISTENT, not REBOOT-VERIFIED"},
    "founder_device_run": {"ladder": "FOUNDER_ACCEPTED", "metrics": metrics.FOUNDER_TIER, "directive": "FOUNDER-USED",
                           "basis": "acceptance.BEYOND_TESTS: FOUNDER_ACCEPTED needs Alfonso's signed acceptance; "
                                    "greg.metrics.founder_tier: signed by the enrolled founder key after its custody "
                                    "attestation; greg.metrics.vepmc counts such a closure only on the body a "
                                    "founder-signed BODY_DESIGNATE named (its founder_body condition)"},
    "external_verification": {"ladder": "EXTERNALLY_VERIFIED", "metrics": metrics.FOUNDER_TIER,
                              "directive": "EXTERNALLY-VERIFIED",
                              "basis": "acceptance.BEYOND_TESTS: an external observation that no test produces; "
                                       "greg.metrics says neither of its levels is an external verification"},
}
TEST_CEILING = TEST_TIERS[-1]                       # what a claim that declares no evidence kind may reach

# Keys are matched after ``field_name`` (any case, camelCase split): "Reality" and "realityLevel" are claim fields.
CLAIM_FIELDS = ("reality", "reality_level", "reality_status", "reality_tier", "current_reality", "acceptance_reality",
                "evidence_level", "evidence_tier", "declared_tier", "attained_tier", "tier", "status",
                "validation_status")
KIND_FIELD, REF_FIELD = "evidence_kind", "evidence_ref"
# What is read: these extensions, in any case, under these top-level directories and under any directory named
# evidence at any depth, plus two files.
SCAN_DIRS = ("docs", "acceptance")
SCAN_SUFFIXES = (".json", ".jsonl", ".yaml", ".yml")
SCAN_FILES = ("greg/path.json", "foundry/completion.yaml")

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

    Total: every directive section-56 level, every greg.mission_control.REALITY label, every greg.metrics level, every
    validation_status of the Outcome contract and every reality label of the cognition SOP (but its NOT_RUNGS) maps
    to a rung of the ladder. Monotone: a stronger label in its own vocabulary's order never maps to a lower rung (the
    SOP's list is no order, so it is checked total only). One label maps to one rung in every vocabulary. A ceiling
    names a rung of the ladder, a greg.metrics level no stronger than that rung, and a section-56 level that crosses
    to no higher rung."""
    levels = directive_levels() if levels is None else levels
    crosswalks = {"directive section 56": (levels, DIRECTIVE_CROSSWALK), "greg.mission_control.REALITY":
                  (REALITY, REALITY_CROSSWALK), "greg.metrics": (METRICS_ORDER, METRICS_CROSSWALK),
                  "contracts/outcome.schema.json validation_status": (outcome_levels(), OUTCOME_CROSSWALK),
                  "docs/PROJECT_COGNITION_SOP.md reality labels": (
                      tuple(label for label in sop_levels() if label not in NOT_RUNGS), SOP_CROSSWALK, False)} \
        if crosswalks is None else crosswalks
    problems = []
    for name, (order, crosswalk, *ordered) in crosswalks.items():
        missing = [label for label in order if label not in crosswalk]
        extra = sorted(set(crosswalk) - set(order))
        if missing or extra:
            problems.append(f"{name}: not total (unmapped {missing}, unknown {extra})")
        rungs = [crosswalk[label] for label in order if label in crosswalk]
        off = [r for r in rungs if r not in LADDER]
        if off:
            problems.append(f"{name}: maps onto {off}, which are not rungs of acceptance.LADDER")
        elif (ordered or [True])[0] and any(rank(a) > rank(b) for a, b in zip(rungs, rungs[1:])):
            problems.append(f"{name}: not monotone: {list(zip(order, rungs))}")
    named = {}
    for crosswalk in [dict(zip(LADDER, LADDER)), LABEL_CROSSWALK, DEVICE_CROSSWALK,
                      *(c for _order, c, *_ in crosswalks.values())]:
        for label, rung in crosswalk.items():
            named.setdefault(label.replace("_", "-").upper(), set()).add(rung)
    problems += [f"{label}: one label maps to several rungs {sorted(rungs)}" for label, rungs in sorted(named.items())
                 if len(rungs) > 1]
    for kind, ceiling in CEILINGS.items():
        if ceiling["ladder"] not in LADDER:
            problems.append(f"ceiling {kind}: {ceiling['ladder']} is not a rung of acceptance.LADDER")
        elif rank(METRICS_CROSSWALK.get(ceiling["metrics"], "COMMERCIAL_OUTCOME_VERIFIED")) > rank(ceiling["ladder"]):
            problems.append(f"ceiling {kind}: greg.metrics {ceiling['metrics']} is above its rung {ceiling['ladder']}")
        if ceiling.get("directive") not in levels:
            problems.append(f"ceiling {kind}: {ceiling.get('directive')!r} is not a section-56 level")
        elif ceiling["ladder"] in LADDER and rank(DIRECTIVE_CROSSWALK.get(
                ceiling["directive"], "COMMERCIAL_OUTCOME_VERIFIED")) > rank(ceiling["ladder"]):
            problems.append(f"ceiling {kind}: section-56 level {ceiling['directive']} is above its rung "
                            f"{ceiling['ladder']}")
    return problems


def _label_pattern(label: str) -> re.Pattern:
    parts = re.split(r"[-_ ]", label)
    body = r"[-_ ]".join(map(re.escape, parts))
    # A compound label of a ladder vocabulary is read in any case ("externally verified"). A one-word label and the
    # informal LABEL_CROSSWALK tokens are read in capitals only: "LIVE", never "a live page"; "FOUNDER-DEVICE", never
    # "founder-device proof". A suffix joined by '-' or '_' keeps the label ("EXTERNALLY_VERIFIED_OUTCOME",
    # "FOUNDER-USED-ON-DEVICE"); a prefix does not ("NON-LIVE").
    any_case = len(parts) > 1 and label not in LABEL_CROSSWALK
    return re.compile(r"(?<![A-Za-z0-9_-])" + body + r"(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9_-])",
                      re.I if any_case else 0)


def _labels() -> dict:
    out = {}
    for crosswalk in (dict(zip(LADDER, LADDER)), DIRECTIVE_CROSSWALK, REALITY_CROSSWALK, METRICS_CROSSWALK,
                      OUTCOME_CROSSWALK, SOP_CROSSWALK, LABEL_CROSSWALK, DEVICE_CROSSWALK):
        for label, rung in crosswalk.items():
            out.setdefault(label.replace("_", "-").upper(), rung)      # one pattern per label, whatever its case
    out.pop("NONE")                                 # "none" in a claim claims nothing
    return out


LABELS = _labels()
PATTERNS = [(label, rung, _label_pattern(label)) for label, rung in LABELS.items()] + [
    ("on the founder's device", "FOUNDER_ACCEPTED", FOUNDER_DEVICE_PHRASE),
    ("DEVICE-VERIFIED", "FOUNDER_ACCEPTED", DEVICE_LIST)]
# "live" in any case where it opens the value or follows a colon ("Live (Linux container rehearsal)", "status: live");
# inside a sentence only "LIVE" is read, so "a live page was rendered" claims nothing.
OPENING_LIVE = re.compile(r"(?:^|:) *(live)(?![A-Za-z0-9_])", re.I)

REHEARSAL = re.compile(r"\brehears\w*|\btest[- ]keys?\b|\bper-test\b|--no-passphrase|\bthrowaway\b|"
                       r"\bsynthetic[- ](?:founder[- ])?authority\b|\bfixtures?\b", re.I)
CONTAINER = re.compile(r"\b(?:containers?|docker|sandbox(?:ed)?)\b", re.I)
# A run of the test machinery itself: what a test, a CI job or a simulation produces is never a founder-device run or
# an external verification. Unit and integration tests are named apart, as the kinds they are; a directory is not a
# kind (tests/unit/ holds tests that drive a real Body process: acceptance/missions.json body_process_tests). "CI" is
# read in capitals only.
UNIT_RUN = re.compile(r"\bunit[- ]tests?\b|\bin-process\b", re.I)
INTEGRATION_RUN = re.compile(r"\bintegration[- ]tests?\b|\btests/integration/", re.I)
TEST_RUN = re.compile(r"\bpytest\b|\bgithub actions\b|\bubuntu-latest\b|\bcontinuous integration\b|"
                      r"\btest (?:runs?|suites?|harness)\b|\bsimulat(?:ed|ion|or)\b|"
                      r"\bmock(?:ed|s)?\b|\bstub(?:bed|s)?\b|\bdry[- ]run\b", re.I)
CI = re.compile(r"(?<![A-Za-z0-9_-])CI(?![A-Za-z0-9_-])")
MARKERS = {"rehearsal": REHEARSAL, "container": CONTAINER, "unit test": UNIT_RUN, "integration test": INTEGRATION_RUN,
           "test run": TEST_RUN, "CI": CI}
# A record that declares no kind is held to the kind its own statement of evidence names: the claim's value and the
# fields that say how it was shown (``EVIDENCE_FIELDS``), never the rest of the record (an acceptance requirement's
# notes name unit tests beside the real-process tests that verify it). The test kind decides over the place: a unit
# test in a container is a unit test; pytest, CI and a simulation name no kind.
EVIDENCE_FIELDS = ("evidence", "how", "run", "runner", "environment", "host")


def implied_kind(hits: dict) -> str | None:
    """The evidence kind a record's own statement of evidence names (``EVIDENCE_FIELDS``), from its run markers."""
    if "unit test" in hits and "integration test" not in hits:
        return "unit_test"
    if "integration test" in hits or "container" in hits:
        return "integration_container"
    return "rehearsal_key" if "rehearsal" in hits else None


CLAUSE_BREAK = re.compile(r"[;.()\[\]{}:!?]|\s[-–—]\s|\bbut\b|\bhowever\b", re.I)
# "above" and "beyond" are not negators: "at or above FOUNDER-USED" and "beyond LOCAL-REAL" claim more, not less.
NEGATORS = re.compile(r"\b(?:not|no|never|nothing|none|without|nor|neither|until|unless|pending|awaiting|requires?|"
                      r"omits?|omitted|lacks?|lacking|missing|absent|"
                      r"required|needs?|needed|cannot|can't|isn't|aren't|wasn't|below|short of|"
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
# The words a negator reaches a label across: function words, labelling verbs and level words, never a content word
# ("never ran on the founder's device, FOUNDER-USED" and "not UNIT-TESTED, FOUNDER-USED" claim FOUNDER-USED).
FILLER = {"a", "an", "the", "be", "been", "being", "is", "are", "was", "were", "yet", "labelled", "labeled", "called",
          "marked", "reported", "claimed", "described", "shown", "treated", "counted", "as", "or", "and", "nor", "at",
          "any", "of", "to", "reach", "reached", "establish", "established", "even", "either", "tier", "level",
          "levels", "higher"}
# Before a place (the founder's-device phrase) or a run marker only, the event that did not happen there: "never ran
# on the founder's device", "not run in a container".
EVENTS = {"run", "ran", "runs", "built", "executed", "used", "tested", "installed", "verified", "deployed",
          "exercised", "observed", "seen", "on", "in", "inside", "within", "under", "with", "using", "via", "own",
          "real"}
DISJUNCTION = {"or", "nor", "/"}
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


def _reaches(between: str, *, place: bool = False, qualifier: bool = False) -> bool:
    """Whether a negator reaches a label across ``between``, the text that separates them: no comma or conjunction,
    only FILLER words (and EVENTS before a ``place``), and every other label in it followed by "or", "nor" or "/"
    ("not FOUNDER-USED or LIVE-BOUNDED"). A label right before a ``qualifier`` (the founder's-device phrase) is the
    label it qualifies: "not REBOOT-VERIFIED on the founder's device"."""
    if COORDINATION.search(between):
        return False
    for _label, _rung, pattern in PATTERNS:
        between = pattern.sub(" \0 ", between)
    allowed, open_label = FILLER | (EVENTS if place else set()), False
    for word in re.findall(r"\0|/|[A-Za-z'’]+", between):
        if word == "\0":
            if open_label:
                return False
            open_label = True
        elif word.lower() in DISJUNCTION:
            open_label = False
        elif word.lower() not in allowed:
            return False
    return qualifier or not open_label


def _negation(text: str, start: int, end: int, *, place: bool = False, qualifier: bool = False) -> str | None:
    """Which rule names the label at [start, end) under a negation in its clause; None when none does.

    Lexical, by declared rule. Clauses break at ; . ( ) [ ] : ! ?, a spaced dash, "but" and "however". The label is
    negated when, in its clause:

    * "before": the nearest negator before it reaches it (``_reaches``): no comma or conjunction between them, only
      filler words, and any other label between them joined by "or" or "nor" ("not FOUNDER-USED", "not
      FOUNDER-USED or LIVE-BOUNDED"; "not UNIT-TESTED, FOUNDER-USED" claims FOUNDER-USED). An event word ("ran",
      "used", "in") is filler only before a place: "never ran on the founder's device" negates the device, "not run in a
      container" the container;
    * "verb": a negator before it governs a labelling verb that is followed only by filler or labels, with no comma or
      conjunction between the two ("Nothing built in a container may be labelled FOUNDER-USED"; "never failed and
      labelled FOUNDER-USED" is a claim);
    * "after": a status that says the label itself is unmet follows it directly or after one colon
      (``NEGATED_AFTER``: "FOUNDER-USED: pending"). This is the weakest rule: ``asserted`` drops it when the record
      describes a container, rehearsal or test run.

    A negation written any other way reads as a claim, so the reader over-reports: "not a container, FOUNDER-USED",
    "FOUNDER-USED, not a container run" and "FOUNDER-USED (not a container run)" are claims. It is still a reader of
    words, not of meaning, and can be phrased around: a sentence whose negator and labelling verb are unrelated but
    joined without a comma or conjunction ("is not a container run labelled FOUNDER-USED") hides the label, and a
    comma list after a prohibited labelling verb is read as one list under the prohibition ("never labelled
    UNIT-TESTED, FOUNDER-USED"). The guard stops mislabelled records; it does not replace reading them."""
    clause = max((m.end() for m in CLAUSE_BREAK.finditer(text, 0, start)), default=0)
    before = text[clause:start]
    negators = list(NEGATORS.finditer(before))
    if negators:
        if _reaches(before[negators[-1].end():], place=place, qualifier=qualifier):
            return "before"
        verbs = list(LABELLING.finditer(before, negators[0].end()))
        if verbs and _only_filler(before[verbs[-1].end():]) and any(
                not COORDINATION.search(before[n.end():verbs[-1].start()]) for n in negators
                if n.end() <= verbs[-1].start()):
            return "verb"
    return "after" if NEGATED_AFTER.match(text[end:end + 80]) else None


def _negated(text: str, start: int, end: int, *, place: bool = False) -> bool:
    return _negation(text, start, end, place=place) is not None


def asserted(value: str, *, after_holds: bool = True) -> list[tuple[str, str]]:
    """(label, rung) for every ladder label the text asserts, in order of appearance. With ``after_holds`` False a
    label negated only by a status after it ("FOUNDER-USED: pending") counts as asserted. An informal label read in
    capitals inside text ("LIVE", never "a live page") is read in any case when it is the whole value; "live" also
    where it opens the value or follows a colon (``OPENING_LIVE``)."""
    value = normalise(value)
    whole = value.strip().upper()
    if whole in LABEL_CROSSWALK:                    # a whole "live" or "founder-device", any case, is that label
        return [(whole, LABEL_CROSSWALK[whole])]
    found = []
    spans = [(label, rung, match.start(), match.end(), pattern is FOUNDER_DEVICE_PHRASE)
             for label, rung, pattern in PATTERNS for match in pattern.finditer(value)]
    spans += [("LIVE", LABEL_CROSSWALK["LIVE"], match.start(1), match.end(1), False)
              for match in OPENING_LIVE.finditer(value)]
    for label, rung, start, end, place in spans:
        if any(s <= start and end <= e and e - s > end - start for _l, _r, s, e, _p in spans):
            continue                                # "LIVE" inside "LIVE-BOUNDED": the longer label is the one read
        negation = _negation(value, start, end, place=place, qualifier=place)
        if negation is None or (negation == "after" and not after_holds):
            found.append((start, label, rung))
    return [(label, rung) for _start, label, rung in sorted(set(found))]


def _markers(text: str) -> dict[str, list[str]]:
    """{marker class: the container, rehearsal, test-key, fixture, unit-test or test-run words of that class the text
    does not negate}, only the classes that occur."""
    text = normalise(text)
    hits = {}
    for name, pattern in MARKERS.items():
        found = [m.group(0) for m in pattern.finditer(text) if not _negated(text, m.start(), m.end(), place=True)]
        if found:
            hits[name] = found
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


@functools.lru_cache(maxsize=1)
def _directive_order() -> tuple[str, ...]:
    return directive_levels()


def above(claims: list, kind: str) -> tuple[str, str, str] | None:
    """(label, rung, why) for the strongest of ``claims`` above what ``kind`` establishes: above its rung, or a
    section-56 level above its section-56 level (directive section 56: "Do not collapse these"). None when none is."""
    ceiling, levels, worst = CEILINGS[kind], _directive_order(), None
    for label, rung in claims:
        level = levels.index(label) if label in levels else -1
        if rank(rung) > rank(ceiling["ladder"]):
            why = f"{kind} establishes at most {ceiling['ladder']} ({ceiling['basis']}); {label} claims {rung}"
        elif level > levels.index(ceiling["directive"]):
            why = (f"{kind} establishes at most {ceiling['directive']} among section 56's levels, which are not "
                   f"collapsed ({ceiling['basis']}); {label} is above it")
        else:
            continue
        if worst is None or (rank(rung), level) > worst[0]:
            worst = ((rank(rung), level), label, rung, why)
    return worst[1:] if worst else None


def check_record(record: dict, field: str, value=None, *, root: Path | None = None,
                 relative: str | None = None) -> list[dict]:
    """The violations of one claim: ``value`` (default ``record[field]``) against the evidence kind its record
    declares, or, when it declares none, against what tests establish and what the run it describes establishes.
    ``root`` and ``relative`` let an ``evidence_ref`` resolve to a file of the scanned tree."""
    value = _get(record, field) if value is None else value
    if not isinstance(value, str):
        return []
    others = [s for key, v in record.items() if field_name(key) != KIND_FIELD for s in _strings(v)]
    hits = _markers("; ".join(others))                                      # "; " ends a clause
    markers = sorted({word for words in hits.values() for word in words})
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
        over = above(claims, kind)
        if over:
            problems.append(over)
        if ceiling in BEYOND_TESTS:
            unchecked = ref_problem(_get(record, REF_FIELD), root, relative)
            if unchecked:
                problems.append((label, rung, f"a {kind} claim names a record a reviewer can check: {unchecked}"))
            if markers:
                problems.append((label, rung, f"declared {kind}, but the record describes a {', '.join(markers)} run"))
        return [{**out, "claimed": claimed, "rung": at, "ceiling": ceiling, "why": why}
                for claimed, at, why in problems]
    if rank(rung) > rank(TEST_CEILING):
        what = f"a {', '.join(markers)} run labelled {label}" if markers else f"{label} ({rung})"
        return [{**out, "ceiling": TEST_CEILING,
                 "why": f"{what}: no declared evidence kind can establish it; without one a claim reaches at most "
                        f"{TEST_CEILING}, what tests establish (acceptance.TEST_TIERS)"}]
    stated = _markers("; ".join([value] + [s for key, v in record.items() if field_name(key) in EVIDENCE_FIELDS
                                           for s in _strings(v)]))
    implied = implied_kind(stated)
    over = above(claims, implied) if implied else None
    if over:
        named = sorted({word for words in stated.values() for word in words})
        return [{**out, "claimed": over[0], "rung": over[1], "kind": None, "implied_kind": implied,
                 "ceiling": CEILINGS[implied]["ladder"],
                 "why": f"no evidence_kind is declared and its evidence is a {', '.join(named)} run, so it is held "
                        f"to {implied}: {over[2]}"}]
    return []


def _pointer(parts) -> str:
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _held(value, parts, chain) -> list[tuple[tuple, str, tuple]]:
    """(pointer parts, string, enclosing records) for every string a claim field holds: itself, the items of a list,
    the fields of a record, at any depth. ``chain`` is the (record, key it was entered by) pairs, outermost first."""
    if isinstance(value, str):
        return [(parts, value, chain)]
    if isinstance(value, dict):
        return [found for key, v in value.items() for found in _held(v, (*parts, key), (*chain, (value, key)))]
    if isinstance(value, (list, tuple)):
        return [found for i, v in enumerate(value) for found in _held(v, (*parts, i), chain)]
    return []


def _record(chain: tuple) -> dict:
    """The record a string is a claim of: its nearest enclosing record, with each field it does not set taken from the
    nearest record around it that does. An outer record's field that leads down to the string is not one of its
    facts: a list of run records under "status" is each run's own, not every run's."""
    merged = {}
    for depth, (record, down) in enumerate(chain):
        for key, value in record.items():
            if depth == len(chain) - 1 or key != down:
                merged[field_name(key)] = value
    return merged


# A JSON Schema's property names and the values its enum, const, default and examples allow are not claims.
SCHEMA_NAMES = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
SCHEMA_VALUES = ("enum", "const", "default", "examples")


def is_schema(data) -> bool:
    """A JSON Schema, by content: a record whose ``$schema`` names json-schema.org (never by file name)."""
    return isinstance(data, dict) and "json-schema.org" in str(data.get("$schema", ""))


def claims_in(data, parts=(), *, root: Path | None = None, relative: str | None = None, _seen=None,
              _schema: bool | None = None) -> list[dict]:
    """Every claim and its violations in one parsed document, with JSON pointers. A string under a claim field is a
    claim of its nearest enclosing record, which takes the fields it does not set (an evidence kind, say) from the
    records around it (``_record``). Each string is read once. A JSON Schema (``is_schema``) is read as one."""
    seen = set() if _seen is None else _seen
    schema = is_schema(data) if _schema is None else _schema
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            field = field_name(key)
            if field not in CLAIM_FIELDS:
                continue
            for where, text, chain in _held(value, (*parts, key), ((data, key),)):
                pointer = _pointer(where)
                if pointer not in seen:
                    seen.add(pointer)
                    found.append({"pointer": pointer, "field": field, "violations": check_record(
                        _record(chain), field, text, root=root, relative=relative)})
        for key, value in data.items():
            if schema and key in SCHEMA_VALUES:
                continue
            if schema and key in SCHEMA_NAMES and isinstance(value, dict):
                for name, sub in value.items():                         # a name, then the schema it names
                    found += claims_in(sub, (*parts, key, name), root=root, relative=relative, _seen=seen,
                                       _schema=True)
                continue
            found += claims_in(value, (*parts, key), root=root, relative=relative, _seen=seen, _schema=schema)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            found += claims_in(value, (*parts, i), root=root, relative=relative, _seen=seen, _schema=schema)
    return found


def scanned(relative: str) -> bool:
    """Whether the guard reads the file at this repository-relative path (``SCAN_DIRS``, ``SCAN_SUFFIXES``,
    ``SCAN_FILES``)."""
    parts = relative.split("/")
    if relative in SCAN_FILES:
        return True
    return parts[-1].lower().endswith(SCAN_SUFFIXES) and (parts[0] in SCAN_DIRS or "evidence" in parts[:-1])


def _files(root: Path) -> list[Path]:
    files = []
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = sorted(d for d in subdirectories if d != ".git")
        for name in names:
            path = Path(directory) / name
            if scanned(path.relative_to(root).as_posix()) and path.is_file():
                files.append(path)
    return sorted(files)


def _load(path: Path):
    """One parsed document; a YAML file of several documents is their list, a JSON Lines file its lines (a blank line
    is None, so a pointer's first index is the line number less one). A byte-order mark is read past."""
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(text)
    if suffix == ".jsonl":
        return [json.loads(line) if line.strip() else None for line in text.splitlines()]
    documents = list(yaml.safe_load_all(text))
    return documents[0] if len(documents) == 1 else documents


def scan(root: Path | str = ROOT, *, allowlist: dict | None = None) -> dict:
    """Every claim in the files ``scanned`` names, checked against its evidence kind; the guard fails when ``failing``
    is non-empty.
    ``ALLOWLIST`` names files of this repository, so it applies only when ``root`` is this checkout."""
    root = Path(root)
    if allowlist is None:
        allowlist = ALLOWLIST if root.resolve() == ROOT else {}
    files, unreadable, claims, violations = _files(root), [], 0, []
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:                    # nesting past the interpreter's recursion limit is unreadable, never a traceback
            found = claims_in(_load(path), root=root, relative=relative)
        except (OSError, ValueError, yaml.YAMLError, RecursionError, MemoryError) as exc:
            unreadable.append({"file": relative, "why": f"unreadable, so no claim in it can be checked: "
                                                        f"{type(exc).__name__}: {str(exc)[:160]}"})
            continue
        for claim in found:
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
