"""The cycle-6 canary script: frozen seeds only, the proposal read from the record, rules applied as declared."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import p8_cr6_canary as C                                        # noqa: E402
from greg.cognition import evolution as E                        # noqa: E402
from greg.cognition.genomes import admission, developmental as D  # noqa: E402


def test_the_canary_seeds_are_fresh_reserved_and_never_a_cycle_split():
    seeds = set(C.SEEDS)
    assert C.SEEDS == tuple(range(8300, 8540)) and seeds <= set(admission.P8_RESERVED)
    used = {s for split in E.CR_SPLITS.values() for part in split for s in part}
    used |= set(E.IMMUNE_TRAIN_SEEDS) | set(E.IMMUNE_HELDOUT_SEEDS) | admission.spent_seeds()
    assert not seeds & used and not seeds & set(range(3000, 4000))
    assert seeds <= E.cr_split_seeds("cycle-6")[2]          # a later split must avoid them


def test_the_guard_refuses_every_other_seed_set():
    for bad in ((8300,), tuple(range(8300, 8539)), (3500,), (7880,), (1000,), (0, 8300)):
        with pytest.raises(C.CanaryError):
            C.guard(bad)
    assert C.guard((0, 1)) == (0, 1)


def test_the_proposal_is_the_cycle_6_record_and_nothing_is_applied():
    record = json.loads(C.RECORD.read_text())
    assert C.proposal() == record["proposal"]["change"]["to"]
    assert record["proposal"]["change"]["from"] == D.CR_DEFAULT_CONFIG           # the incumbent is unchanged


def test_decide_applies_the_declared_rules():
    def row(wins, losses, a, b):
        return {"wins": wins, "losses": losses, "sign_test_p_one_sided": E.sign_test(wins, losses),
                "mean_a": a, "mean_b": b}
    good, restart_even = row(130, 80, 0.005, 0.008), row(100, 100, 0.005, 0.005)
    assert C.decide(good, restart_even, True)["verdict"] == "CANARY_PASSES"
    assert C.decide(good, restart_even, False)["verdict"] == "CANARY_FAILS"
    assert C.decide(row(130, 80, 0.009, 0.008), restart_even, True)["verdict"] == "CANARY_FAILS"   # higher mean
    assert C.decide(row(105, 100, 0.005, 0.008), restart_even, True)["verdict"] == "CANARY_FAILS"  # not significant
    assert C.decide(good, row(80, 130, 0.006, 0.005), True)["verdict"] == \
        "CANARY_PASSES_BUT_RANDOM_RESTART_IS_BETTER"
    assert C.decide(good, row(80, 130, 0.004, 0.005), True)["verdict"] == "CANARY_PASSES"      # restart mean higher
    assert all(C.decide(good, restart_even, ok)["applied"] is False for ok in (True, False))


def test_measure_runs_end_to_end_on_development_seeds():
    out = C.measure((0, 1))
    assert out["n"] == 2 and set(out["mean_loss"]) == {"incumbent", "proposed", "random_restart"}
    assert out["proposed"]["config"] == C.proposal() and out["decision"]["applied"] is False
    assert out["stress"]["all_outputs_verified"] is True
