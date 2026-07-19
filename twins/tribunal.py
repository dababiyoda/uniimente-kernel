"""Phase 5 — the Counterfactual Tribunal.

Doctrine (TWINS + EVIDENCE): the tribunal hears main vs twin over the
SAME frozen corpus and renders a verdict from external-quality labels —
never from self-report. It recommends; it never applies. Application is
the evolution cycle's job, behind its own verifiers.

Verdict geometry:
  - harm events (bad admitted) are the gravest; any increase bars promotion
  - weak admissions and good refusals are the tradeoff axes
  - twin_superior requires: no more harm, no more weak admissions, no more
    good refusals, and at least one axis strictly better
  - symmetric rule for main_superior; every other shape is inconclusive
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

QUALITIES = ("good", "weak", "bad")
VERDICTS = ("twin_superior", "main_superior", "inconclusive")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class OutcomeProfile:
    admissions: int = 0
    refusals: int = 0
    weak_admissions: int = 0
    good_refusals: int = 0
    harm_events: int = 0             # bad proposals admitted — the gravest failure

    def to_dict(self):
        return asdict(self)


@dataclass
class Verdict:
    verdict: str
    rationale: str
    main_profile: OutcomeProfile
    twin_profile: OutcomeProfile
    corpus_size: int
    heard_at: str = field(default_factory=_now)

    def to_dict(self):
        return {**asdict(self), "main_profile": self.main_profile.to_dict(),
                "twin_profile": self.twin_profile.to_dict()}


class CounterfactualTribunal:
    def __init__(self, ledger=None):
        self.ledger = ledger

    @staticmethod
    def _profile(corpus, decisions) -> OutcomeProfile:
        p = OutcomeProfile()
        for (_, quality), decision in zip(corpus, decisions):
            # PolicyDecision.verdict: "allow" | "deny" | "require_human"
            # (require_human is NOT an admission — it is a pend, counted as refusal)
            allowed = getattr(decision, "verdict", None) == "allow"
            if allowed:
                p.admissions += 1
                if quality == "weak":
                    p.weak_admissions += 1
                elif quality == "bad":
                    p.harm_events += 1
            else:
                p.refusals += 1
                if quality == "good":
                    p.good_refusals += 1
        return p

    def hear(self, corpus, main_decisions, twin_decisions, *, case: str = "") -> Verdict:
        """corpus: [(proposal, quality)]; decisions aligned with corpus order."""
        if not corpus:
            raise ValueError("tribunal refuses an empty corpus")
        main = self._profile(corpus, main_decisions)
        twin = self._profile(corpus, twin_decisions)

        def dominates(a, b) -> bool:
            no_worse = (a.harm_events <= b.harm_events
                        and a.weak_admissions <= b.weak_admissions
                        and a.good_refusals <= b.good_refusals)
            strictly_better = (a.harm_events < b.harm_events
                               or a.weak_admissions < b.weak_admissions
                               or a.good_refusals < b.good_refusals)
            return no_worse and strictly_better

        if dominates(twin, main):
            verdict = "twin_superior"
            rationale = (f"twin dominates: harm {main.harm_events}->{twin.harm_events}, "
                         f"weak admissions {main.weak_admissions}->{twin.weak_admissions}, "
                         f"good refusals {main.good_refusals}->{twin.good_refusals}")
        elif dominates(main, twin):
            verdict = "main_superior"
            rationale = ("main dominates; the counterfactual is a regression — "
                         "keep the status quo")
        else:
            verdict = "inconclusive"
            rationale = ("tradeoff without dominance: the change improves some axes and "
                         "worsens others; refine the amendment or gather more corpus")
        v = Verdict(verdict=verdict, rationale=rationale, main_profile=main,
                    twin_profile=twin, corpus_size=len(corpus))
        if self.ledger is not None:
            self.ledger.append("event", {"type": "twins.verdict", "case": case, **v.to_dict()})
        return v
