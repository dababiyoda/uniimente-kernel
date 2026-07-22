"""Distribution measured by owned relationships and useful action.

The ranking function is informed return, not watch time. Impressions
without owned relationships and behavior change are false closure and can
trigger organ termination.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from closure.whole_body import Loop, LoopEvidence, WholeBodyClosureController

USEFUL_ACTIONS = ("used_tool", "cited_source", "taught_method",
                  "completed_node", "joined_community", "purchased")


@dataclass
class DistributionWindow:
    company: str
    window_id: str
    impressions: int = 0
    qualified_visits: int = 0
    owned_relationships: int = 0
    useful_actions: dict[str, int] = field(default_factory=dict)
    returning_visitors: int = 0

    def record_impressions(self, n: int) -> None:
        self.impressions += int(n)

    def record_qualified_visit(self, n: int = 1) -> None:
        self.qualified_visits += int(n)

    def record_owned_relationship(self, n: int = 1) -> None:
        self.owned_relationships += int(n)

    def record_useful_action(self, kind: str, n: int = 1) -> None:
        if kind not in USEFUL_ACTIONS:
            raise ValueError(f"{kind!r} is not a useful action; attention metrics do not count as behavior change")
        self.useful_actions[kind] = self.useful_actions.get(kind, 0) + int(n)

    def record_returning_visitor(self, n: int = 1) -> None:
        self.returning_visitors += int(n)

    @property
    def behavior_changes(self) -> int:
        return sum(self.useful_actions.values())

    def informed_return(self) -> float:
        if self.returning_visitors == 0:
            return 0.0
        return self.behavior_changes / self.returning_visitors


class DistributionLoop:
    def __init__(self, company: str, *, ledger=None):
        self.company = company
        self.ledger = ledger
        self.windows: list[DistributionWindow] = []

    def open_window(self, window_id: str) -> DistributionWindow:
        w = DistributionWindow(company=self.company, window_id=window_id)
        self.windows.append(w)
        return w

    def evaluate(self, window: DistributionWindow):
        ev = LoopEvidence(
            internal_ok=window.impressions > 0,
            external_ok=window.owned_relationships > 0 and window.behavior_changes > 0,
            detail=(f"impressions={window.impressions} owned={window.owned_relationships} "
                    f"behavior_changes={window.behavior_changes} "
                    f"informed_return={window.informed_return():.2f}"))
        result = WholeBodyClosureController().applicable(
            f"distribution:{self.company}:{window.window_id}",
            {Loop.DISTRIBUTION: ev}, applicable={Loop.DISTRIBUTION})
        if self.ledger is not None:
            self.ledger.append("event", {"type": "foundry.distribution_evaluated",
                                         "company": self.company,
                                         "window": window.window_id,
                                         "overall": result.overall,
                                         "detail": ev.detail})
        return result

    def kill_condition_met(self, *, consecutive: int = 2) -> bool:
        if len(self.windows) < consecutive:
            return False
        tail = self.windows[-consecutive:]
        impressions_growing = all(w.impressions > 0 for w in tail) and (
            len(tail) == 1 or tail[-1].impressions >= tail[0].impressions)
        no_behavior_change = all(w.behavior_changes == 0 for w in tail)
        return impressions_growing and no_behavior_change
