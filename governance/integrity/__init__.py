"""Live constitutional integrity — is the Constitution what it was authorised to be?

Created 2026-08-23 under FOUNDER-RULING-2026-08-23, CONTRADICTION-0002 Option A.

## Why this exists

Until today the institution's only tripwire on constitutional change was a side
effect of a *sealed historical experiment*. `evolution/repair/spec.py` pinned
twelve artifacts — the five constitutional documents, the three authority
documents, the three identity registries and the Consequence Gate — and a test
asserted those freeze-time hashes against the **live** files.

That fused two duties which pull in opposite directions:

1. *Reproduce a historical run.* Wants freeze-time bytes, forever.
2. *Notice unauthorised constitutional change.* Wants today's bytes, compared
   against what is authorised **today**.

Fused, the institution could not lawfully amend its own constitution without a
sealed experiment failing — growth read as breakage. The founder ruled the two
apart: the experiment now reads byte-identical frozen copies
(`evolution/repair/continuity/`), and this module takes duty 2.

## The property this module actually enforces

`constitution/amendment-policy.ucl` already states the law:

    hard_rules { no_silent_amendment = true }

and the ratification step requires *"a signed decision record with constitution
hash before and after"*. That was prose. Here it is arithmetic.

Every watched artifact has a **genesis hash** and an append-only chain of
**amendment records**, each naming the hash before, the hash after, the founder
authorisation, and the reason. The authorised baseline is not a stored value —
it is *computed* by replaying that chain from genesis. So:

- Changing a file without adding a record → `UNAUTHORISED_CHANGE`.
- Adding a record whose `from_sha256` does not match the chain → the replay
  refuses, and every verdict becomes unavailable rather than convenient.
- Editing a historical record to make today's bytes fit → breaks the chain at
  that link.
- Adding a constitutional file nobody declared → `UNGOVERNED_ADDITION`.

There is no code path that writes an amendment record. Authorisation enters this
module the way the Constitution says it must: a human edits the source, naming a
ruling that exists on disk. A module that could mint its own authorisation would
be the exact self-expansion the standing rules forbid.

## What this module deliberately does not do

It does not import `evolution.repair.spec`. The twelve genesis hashes below are
stated independently, and duplicating twelve hex strings is the correct price:
an import would re-fuse the two mechanisms the founder just separated, and the
next constitutional amendment would once again have to move a sealed
experiment's baseline. `test_governance_integrity.py` asserts the independence
structurally.

It does not decide whether an amendment was *wise*, and it holds no authority to
block one. It reports. Blocking is the Consequence Gate's job, ratification is
Alfonso's, and this module is neither.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from enum import Enum

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

#: Directories whose contents are constitutional in character. Used to detect
#: *additions* — a new file here is a constitutional change even though no
#: baseline entry moved.
WATCHED_TREES = {
    "constitution": (".ucl",),
    "authority": (".yaml",),
}


@dataclass(frozen=True)
class Amendment:
    """One authorised change to one constitutional artifact.

    `authorization` must name a document under `docs/` that records a founder
    decision. It is checked for existence, not parsed: this module verifies that
    an authorisation was *cited*, and a human reading the citation verifies that
    it says what the amendment claims. Machine-checking the semantics of a
    ruling would be this module deciding what the founder meant.
    """

    artifact: str
    from_sha256: str
    to_sha256: str
    #: Path, relative to the kernel root, of the founder decision authorising it.
    authorization: str
    date: str
    reason: str


#: Hash of each artifact at the moment this baseline was established
#: (2026-08-23). Every one was verified byte-identical to the live tree when it
#: was written down; `test_governance_integrity.py` re-proves the chain.
#:
#: These values coincide with `evolution.repair.spec.CONTINUITY_ARTIFACT_SHA256`
#: because the live tree happened to still sit on its freeze-time bytes today.
#: That coincidence is temporary and must never become an import — see the
#: module docstring.
GENESIS_SHA256 = {
    "constitution/constitution.ucl":
        "5c269850d8da799db66030103c52a175596d9c5f3bb61d25f54d7da9dde2ecd0",
    "constitution/sovereignty.ucl":
        "dc44c1f4304d42791a9db634796584531d40ba6b46191f2cba3877e48ee7fbcc",
    "constitution/shutdown-policy.ucl":
        "e3b443663cc5ed81a8b8827d8feb49962f82f262e85c282113f534c2afab2e54",
    "constitution/amendment-policy.ucl":
        "0132d53ec1e770a526f0e57888235a0b0bac4ed14b443782da537fb70b2ac01f",
    "constitution/participant-rights.ucl":
        "feba5d83800cd5d04702087473eea4d38290950097072efc578cfd498d631687",
    "authority/authority-matrix.yaml":
        "bd763098ecbbfd6ea7e8c9d80b83ed329fefd4766e53ed9b11006719fc671a45",
    "authority/legal-principals.yaml":
        "bdbe881c32353ec3546c459f7250f2bc34b40b014e7fe661f36281c7b9af5061",
    "authority/reserved-matters.yaml":
        "f185e0d11dec25e2bc3dbb73ce92bbb5d276358d1ac8abcaca7526a2805eb924",
    "identity/organ-registry.yaml":
        "7a78955247df0d8204959d0cbb38b05d6e49578e3c0a9f3f0f7d0c916fcebb40",
    "identity/agent-registry.yaml":
        "5c8b7b4775299c2c3943a4e3432798b1f864fada0070f4a5f3699400d95cd7fd",
    "identity/service-identities.yaml":
        "cd8c2c493b22a25926bbcedb049ebe28d86bd6e087ab920c0bbe2bae08cceac0",
    "policy/consequence_gate.py":
        "0b133b57eea1e349db63c8edf3ad9514d934e7b0b11f67cad0c9adc4b78a63ce",
}

#: Append-only. Never edit a landed record: to correct one, add another.
#: Ordering matters — records for the same artifact replay in list order.
AMENDMENTS: tuple[Amendment, ...] = (
    Amendment(
        artifact="policy/consequence_gate.py",
        from_sha256="0b133b57eea1e349db63c8edf3ad9514d934e7b0b11f67cad0c9adc4b78a63ce",
        to_sha256="3b78eb2f4378dc3c99ada3215d24ceb9e04c675e33f0d538cb7a5e44e3cc1f0e",
        authorization="docs/deliberations/"
                      "FOUNDER-RULING-2026-08-23-infinite-goal-chase.md",
        date="2026-08-23",
        reason=(
            "Two changes, both authorised by the same ruling. (1) Witness v2 "
            "live emission: the Gate passes evidence_confidence, "
            "consequence_class, exposure_ceiling_usd and "
            "predicted_success_probability into new_witness — values it "
            "already held and dropped. (2) The `authorized` criterion from "
            "CONTRADICTION-0003 Option B: the Gate no longer issues its own "
            "grant for a consequence class that reaches outside. The second "
            "was found only because the first removed what hid it — the "
            "evidence floor had been refusing external proposals before the "
            "capability step could be reached. This record is the first "
            "amendment in the chain; the live tripwire caught the edit and "
            "required it."),
    ),
)


class Verdict(str, Enum):
    INTACT = "INTACT"
    #: Live bytes differ from the authorised baseline and no record explains it.
    UNAUTHORISED_CHANGE = "UNAUTHORISED_CHANGE"
    #: Declared in the baseline, absent from disk.
    MISSING = "MISSING"
    #: Present in a watched tree, declared nowhere.
    UNGOVERNED_ADDITION = "UNGOVERNED_ADDITION"


class BrokenChain(Exception):
    """An amendment record does not follow from the state before it.

    Raised rather than resolved. A baseline that repaired its own chain would
    let a bad record become truth by being written twice.
    """


@dataclass(frozen=True)
class ArtifactStatus:
    artifact: str
    verdict: Verdict
    authorized_sha256: str | None
    observed_sha256: str | None
    #: How many authorised amendments this artifact has accumulated.
    amendments: int

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.INTACT


@dataclass(frozen=True)
class IntegrityReport:
    statuses: tuple[ArtifactStatus, ...]

    @property
    def intact(self) -> bool:
        """True only when every watched artifact is where it was authorised."""
        return all(s.ok for s in self.statuses)

    @property
    def findings(self) -> tuple[ArtifactStatus, ...]:
        return tuple(s for s in self.statuses if not s.ok)

    @property
    def headline(self) -> str:
        n = len(self.statuses)
        bad = len(self.findings)
        if bad == 0:
            return f"{n} constitutional artifacts, all as authorised"
        return f"{n} constitutional artifacts, {bad} FINDING(S)"


def authorized_baseline(
        amendments: tuple[Amendment, ...] = AMENDMENTS) -> dict[str, str]:
    """Replay genesis + amendments into the hash each artifact is authorised to
    have **today**.

    Computed, never stored. A stored baseline can be edited in the same commit
    as the file it authorises; a replayed one cannot, because the record that
    moves it has to state the hash it moves *from*.
    """
    baseline = dict(GENESIS_SHA256)
    for i, am in enumerate(amendments):
        if am.artifact not in baseline:
            raise BrokenChain(
                f"amendment {i} amends {am.artifact!r}, which has no genesis "
                "hash. Add it to GENESIS_SHA256 first, or correct the path.")
        current = baseline[am.artifact]
        if am.from_sha256 != current:
            raise BrokenChain(
                f"amendment {i} for {am.artifact} claims to start from "
                f"{am.from_sha256[:12]}… but the chain is at {current[:12]}…. "
                "Records are append-only: add a record that follows from the "
                "current state rather than editing history.")
        baseline[am.artifact] = am.to_sha256
    return baseline


def _sha256_of(path: str) -> str | None:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except FileNotFoundError:
        return None


def _amendment_count(artifact: str,
                     amendments: tuple[Amendment, ...]) -> int:
    return sum(1 for a in amendments if a.artifact == artifact)


def _ungoverned_additions(root: str, declared: set[str]) -> list[str]:
    """Files in a watched tree that no baseline entry declares."""
    found = []
    for tree, suffixes in sorted(WATCHED_TREES.items()):
        directory = os.path.join(root, tree)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(suffixes):
                continue
            rel = f"{tree}/{name}"
            if rel not in declared:
                found.append(rel)
    return found


def verify(root: str = KERNEL_ROOT,
           amendments: tuple[Amendment, ...] = AMENDMENTS) -> IntegrityReport:
    """Read the live constitutional artifacts and compare against what is
    authorised. Raises `BrokenChain` if the amendment record itself is unsound.
    """
    baseline = authorized_baseline(amendments)
    statuses: list[ArtifactStatus] = []

    for artifact, expected in sorted(baseline.items()):
        observed = _sha256_of(os.path.join(root, artifact))
        if observed is None:
            verdict = Verdict.MISSING
        elif observed == expected:
            verdict = Verdict.INTACT
        else:
            verdict = Verdict.UNAUTHORISED_CHANGE
        statuses.append(ArtifactStatus(
            artifact=artifact, verdict=verdict, authorized_sha256=expected,
            observed_sha256=observed,
            amendments=_amendment_count(artifact, amendments)))

    for rel in _ungoverned_additions(root, set(baseline)):
        statuses.append(ArtifactStatus(
            artifact=rel, verdict=Verdict.UNGOVERNED_ADDITION,
            authorized_sha256=None,
            observed_sha256=_sha256_of(os.path.join(root, rel)),
            amendments=0))

    return IntegrityReport(statuses=tuple(statuses))
