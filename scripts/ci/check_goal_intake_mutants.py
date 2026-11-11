"""Each safeguard of Goal Gravity's intake count (directive section 42, unit S42-B) must fail its tests when removed.

    python scripts/ci/check_goal_intake_mutants.py

A goal's untrusted intake adds up by independent source and never by volume (greg/goal_gravity.py,
``IntakeAccumulation``), with the data plane's source weighting and campaign cap (greg/dataplane.py). Mutants are
applied in a scratch copy of the repository, never to the working tree; the copy runs without bytecode and its
__pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_goal_intake_accumulation.py reports a FAILED test (an import or collection error does not
count). Exit status 1 if any mutant survives or no longer applies.

Not mutated: ``dataplane.claim_key`` as Goal Gravity uses it. It is the name under which a wording's placement is
remembered inside one count; a wording that misses it is placed again by its words and lands in the same claim, so
removing its normalisation changes no wake (the data plane's own tests cover the key).
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
GRAVITY = "greg/goal_gravity.py"
DATAPLANE = "greg/dataplane.py"
TESTS = "tests/unit/test_greg_goal_intake_accumulation.py"
MUTANTS = [
    # what counts
    (GRAVITY, "chatter on the goal's channel that names nothing adds up",
     "    if not named:\n        bare = {k: v", "    if False:\n        bare = {k: v"),
    (GRAVITY, "a quarantined item adds weight",
     '        if p.get("quarantined") or at is None:', "        if at is None:"),
    (GRAVITY, "an item with no readable time is counted",
     '        if p.get("quarantined") or at is None:', '        if p.get("quarantined"):'),
    (GRAVITY, "a goal counts what arrived before it was authorized",
     "        self.reports: dict[str, deque] = {}       # goal -> its latest relevant reports, in ledger order\n",
     "        self.reports = {g: deque(maxlen=INTAKE_WINDOW_ITEMS) for g in registry.goals()}\n"),
    (GRAVITY, "a report from before the goal is dropped instead of judged alone",
     "            return own       # recorded before", "            return 0.0       # recorded before"),
    # one unit per independent source per claim
    (GRAVITY, "one source repeating its claim adds again",
     "        if report.source not in side.sources \\\n", "        if True \\\n"),
    (GRAVITY, "a campaign adds past the data plane's cap",
     "                and dataplane.claim_support(len(side.sources) + 1) > dataplane.claim_support(len(side.sources)):",
     "                and True:"),
    (DATAPLANE, "the data plane's cap is gone, and Goal Gravity's with it",
     "    return min(sources, max(1, campaign_sources - 1))", "    return sources"),
    # a wake spends what had arrived; a repeat is never news
    (GRAVITY, "a wake spends nothing", "        side.spent = side.spent or spent\n", "        side.spent = side.spent\n"),
    (GRAVITY, "the goal's wake record is never read",
     '            elif rec.record_type == GoalRegistry.TRANSITION_RECORD and "signal_ids" in rec.payload:',
     "            elif False:"),
    (GRAVITY, "a report that adds nothing wakes the goal on what others left",
     "        return sum(added.values()) if added.get(event_id, 0.0) > 0 else 0.0",
     "        return sum(added.values())"),
    # the same claim reworded, and the same claim denied
    (GRAVITY, "a reworded copy is a new claim",
     "    return bool(union) and len(a & b) / union >= NEAR_DUPLICATE", "    return bool(union) and a == b"),
    (GRAVITY, "the declared resemblance of 0.8 is itself excluded",
     "    return bool(union) and len(a & b) / union >= NEAR_DUPLICATE",
     "    return bool(union) and len(a & b) / union > NEAR_DUPLICATE"),
    (GRAVITY, "a claim's words are not the data plane's normalised words",
     "_norm(_plain_not(content)).split()", "_plain_not(content).split()"),
    (GRAVITY, "a denial counts as agreement",
     "                placed[report.key] = (claim, claim.sides[int(denied)])",
     "                placed[report.key] = (claim, claim.sides[0])"),
    (GRAVITY, "the two sides of a claim add to each other",
     "        return max((side.weight for side in self.sides if not side.spent), default=0.0)",
     "        return sum(side.weight for side in self.sides if not side.spent)"),
    (GRAVITY, "a contracted denial is not seen as one",
     '    return _CONTRACTED_NOT.sub(" not", text)\n', "    return text\n"),
    (GRAVITY, "negations stay in a claim's words, so a short denial is a new claim",
     " if w not in restatement.NEGATORS)", ")"),
    # the signed window, the founder's mute, the bounds
    (GRAVITY, "the signed window never expires",
     "                if report.at <= start or report.channel in muted:", "                if report.channel in muted:"),
    (GRAVITY, "a muted channel's reports add to others",
     "                if report.at <= start or report.channel in muted:", "                if report.at <= start:"),
    (GRAVITY, "a goal keeps every report for ever",
     "                                        deque(maxlen=INTAKE_WINDOW_ITEMS))",
     "                                        deque())"),
    (GRAVITY, "a report keeps every word",
     "    return frozenset(list(words)[:INTAKE_CLAIM_WORDS])", "    return frozenset(words)"),
    # the count kept between reports follows the ledger
    (GRAVITY, "a kept count is never counted again",
     "        if self._folded.get(spec.goal_id, (None,))[0] != state:",
     "        if spec.goal_id not in self._folded:"),
    (GRAVITY, "a kept count ignores the founder's mute",
     "        state = (reports[-1].position, muted)", "        state = (reports[-1].position,)"),
    # the founder's view
    (GRAVITY, "the founder's view counts a spent report as waiting",
     "if r.event_id in added and r.position > woken]", "if r.event_id in added]"),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="goal-intake-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
