"""Resilience evidence and decoupling warnings from a synthetic GREG journal (directive sections 21-22)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from greg import resilience as R

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


class Journal:
    def __init__(self):
        self.events = []

    def add(self, kind, minutes, **payload):
        at = (T0 + timedelta(minutes=minutes)).isoformat()
        self.events.append(SimpleNamespace(type="greg." + kind, payload={**payload, "at": at}, occurred_at=at,
                                           event_id=f"ev-{len(self.events)}"))
        return self

    def id_of(self, kind, **match):
        return next(e.event_id for e in self.events if e.type == "greg." + kind
                    and all(e.payload.get(k) == v for k, v in match.items()))

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix)]


def exclude(j, minutes, mission_id, action_id, critique_id="crit-1", reason="times out"):
    """The engine's path: a founder critique of the action, then the exclusion citing it."""
    j.add("critique.recorded", minutes, critique_id=critique_id,
          target_event_id=j.id_of("mission.action", mission_id=mission_id, action_id=action_id))
    return j.add("mission.strategy_excluded", minutes, mission_id=mission_id, action_id=action_id, reason=reason,
                 critique_ref=critique_id)


def actions(j, cap, statuses, start=0, mission="m1", step=10):
    for i, status in enumerate(statuses):
        j.add("mission.action", start + i * step, mission_id=mission, action_id=f"{cap}-{i}", capability=cap,
              status=status)
    return j


def test_episodes_measure_recovery_recurrence_and_founder_intervention():
    j = Journal()
    j.add("mission.observed", 0, mission_id="m1", check_id="c", passed=False)
    j.add("mission.action", 5, mission_id="m1", action_id="fix", capability="fs.write", status="DONE")
    j.add("mission.observed", 10, mission_id="m1", check_id="c", passed=True)
    j.add("mission.observed", 20, mission_id="m1", check_id="c", passed=False)
    j.add("decision.answered", 25, mission_id="m1", request_id="r1", answer="approve")
    j.add("mission.action", 26, mission_id="m1", action_id="fix2", capability="fs.write", status="DONE")
    j.add("mission.observed", 30, mission_id="m1", check_id="c", passed=True)
    eps = R.episodes(j)
    assert [e["seconds"] for e in eps] == [600.0, 600.0]
    assert [e["recurrence"] for e in eps] == [False, True]
    assert [e["founder_intervened"] for e in eps] == [False, True]
    s = R.summary(j)["episodes"]
    assert s["recovered"] == 2 and s["recurrence_rate"] == 0.5 and s["recovered_without_founder"] == 0.5
    assert s["recovery_path_diversity"] == {"m1/c": 2}


def test_antifragility_needs_improvement_after_failures_and_a_learning_record():
    j = actions(Journal(), "tool.x", ["FAILED", "FAILED", "FAILED"] + ["DONE"] * 6)
    assert R.after_failure(j)["tool.x"]["verdict"] == "IMPROVED_AFTER_FAILURE_WITHOUT_LEARNING_RECORD"
    j.add("critique.regression_closed", 15, critique="tool.x timeout")         # names nothing attributable
    assert R.after_failure(j)["tool.x"]["verdict"] == "IMPROVED_AFTER_FAILURE_WITHOUT_LEARNING_RECORD"
    j.add("mission.strategy_excluded", 25, mission_id="m1", action_id="tool.x-1", reason="no critique cited")
    assert R.after_failure(j)["tool.x"]["verdict"] == "IMPROVED_AFTER_FAILURE_WITHOUT_LEARNING_RECORD"
    exclude(j, 26, "m1", "tool.x-1")
    assert R.after_failure(j)["tool.x"]["verdict"] == "ANTIFRAGILE_EVIDENCE"


def test_redundancy_alone_is_not_antifragility_and_degradation_is_fragile():
    j = actions(Journal(), "tool.y", ["DONE"] * 5 + ["FAILED"] * 3)
    assert R.after_failure(j)["tool.y"]["verdict"] == "FRAGILE"
    few = actions(Journal(), "tool.z", ["DONE", "FAILED", "DONE"])
    assert R.after_failure(few)["tool.z"]["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "fragile: tool.y" in R.summary(j)["warnings"]


def test_one_capability_failing_across_missions_is_a_common_cause_candidate():
    j = Journal()
    j.add("mission.action", 0, mission_id="m1", action_id="a", capability="net.fetch", status="FAILED")
    j.add("mission.action", 7, mission_id="m2", action_id="b", capability="net.fetch", status="ERROR")
    j.add("mission.action", 200, mission_id="m3", action_id="c", capability="fs.read", status="FAILED")
    causes = R.common_causes(j)
    assert causes == [{"capability": "net.fetch", "missions": ["m1", "m2"], "first_at": T0.isoformat(), "failures": 2}]


def test_a_local_metric_rising_while_the_system_degrades_is_flagged():
    j = Journal()
    for day in range(5):
        minutes = day * 24 * 60
        for k in range(5):
            j.add("mission.action", minutes + k, mission_id="m1", action_id=f"a{day}{k}", capability="tool.y",
                  status="DONE" if k < day + 1 else "FAILED")
            j.add("mission.observed", minutes + k, mission_id="m1", check_id=f"c{k}", passed=k < 5 - day)
    flags = R.decoupling_from_journal(j)
    assert flags[0]["capability"] == "tool.y" and flags[0]["state"] == "DECOUPLING_WARNING"
    assert any(w.startswith("decoupling: tool.y") for w in R.summary(j)["warnings"])
    assert R.decoupling([(0, 1), (1, 2)], [(0, 1), (1, 0)])["state"] == "INSUFFICIENT_EVIDENCE"


def test_concentration_and_the_read_only_contract():
    j = actions(Journal(), "a", ["DONE"] * 3)
    actions(j, "b", ["DONE"], start=100)
    c = R.concentration(j)
    assert c["top"] == {"capability": "a", "share": 0.75} and c["herfindahl"] == 0.625
    s = R.summary(j)
    assert s["induces_failures"] is False and s["writes"] == 0


def test_cli_without_a_body_reports_no_ledger(tmp_path, capsys):
    import json
    from greg import cli
    assert cli.main(["--home", str(tmp_path / "none"), "resilience"]) == 0
    assert json.loads(capsys.readouterr().out)["reality_status"] == "NO_BODY_LEDGER"


def test_learning_elsewhere_or_a_mere_proposal_never_earns_antifragility():
    j = actions(Journal(), "tool.x", ["FAILED", "FAILED", "FAILED"] + ["DONE"] * 6)
    j.add("improvement.proposed", 15, capability="tool.x", candidate_id="c1")            # a proposal, not learning
    j.add("mission.strategy_excluded", 15, mission_id="m9", action_id="other", reason="x")  # another mission
    j.add("improvement.evaluated", 15, capability="tool.y", candidate_id="c2")            # another capability
    assert R.after_failure(j)["tool.x"]["verdict"] == "IMPROVED_AFTER_FAILURE_WITHOUT_LEARNING_RECORD"
    early = actions(Journal(), "tool.x", ["FAILED", "FAILED", "FAILED"] + ["DONE"] * 6, start=60)
    early.add("improvement.evaluated", 0, capability="tool.x", candidate_id="c3")        # before any failure
    assert R.after_failure(early)["tool.x"]["learning_artifact_after_failure"] is False
    early.add("improvement.evaluated", 90, capability="tool.x", candidate_id="c4")       # named, after failure
    assert R.after_failure(early)["tool.x"]["verdict"] == "ANTIFRAGILE_EVIDENCE"


def test_the_engines_own_failure_statuses_count_and_policy_refusals_do_not():
    # review 2026-10-13: the engine writes REFUSED (with a receipt) and UNAVAILABLE, never FAILED or ERROR,
    # so a real capability failing four times reported zero failures
    j = Journal()
    for i, status in enumerate(["REFUSED", "REFUSED", "UNAVAILABLE"]):
        j.add("mission.action", i * 10, mission_id="m1", action_id=f"w{i}", capability="fs.write", status=status,
              receipt=f"sha256:{i}" if status == "REFUSED" else None)
    j.add("mission.action", 40, mission_id="m1", action_id="p", capability="fs.write", status="REFUSED", receipt=None)
    for i in range(6):
        j.add("mission.action", 50 + i, mission_id="m1", action_id=f"ok{i}", capability="fs.write", status="DONE")
    assert R.after_failure(j)["fs.write"]["failures"] == 3          # the policy refusal is not the capability's
    j.add("mission.action", 5, mission_id="m2", action_id="x", capability="fs.write", status="REFUSED",
          receipt="sha256:x")
    assert R.common_causes(j)[0]["missions"] == ["m1", "m2"]


def test_learning_is_attributed_through_the_lever_and_the_critiqued_attempt():
    from greg import improvement
    cap = improvement.CAPABILITY
    lever = next(iter(improvement.LEVERS))
    j = actions(Journal(), cap, ["UNCERTAIN"] * 3 + ["DONE"] * 6)
    j.add("improvement.evaluated", 35, candidate_id="c1", lever=lever, case_id="k", errors=0)   # the real shape
    assert R.after_failure(j)[cap]["verdict"] == "ANTIFRAGILE_EVIDENCE"
    retried = Journal()
    retried.add("mission.action", 0, mission_id="m1", action_id="a", capability="tool.x", status="UNCERTAIN")
    retried.add("mission.action", 10, mission_id="m1", action_id="a", capability="tool.x", status="DONE")
    for i, status in enumerate(["UNCERTAIN", "UNCERTAIN"] + ["DONE"] * 6):
        retried.add("mission.action", 20 + 10 * i, mission_id="m1", action_id=f"b{i}", capability="tool.x",
                    status=status)
    # the founder critiques the SUCCESSFUL retry and excludes the strategy: not learning from failure
    retried.add("critique.recorded", 200, critique_id="crit-x",
                target_event_id=retried.id_of("mission.action", action_id="a", status="DONE"))
    retried.add("mission.strategy_excluded", 200, mission_id="m1", action_id="a", reason="sloppy",
                critique_ref="crit-x")
    assert R.after_failure(retried)["tool.x"]["learning_artifact_after_failure"] is False
