"""Hostile probes of the stress gate as it stands at a given checkout (argv[1]).

`inline` is the cycle()'s adversarial aggregation copied verbatim from 239a87f (evolution.py lines 1067-1078), so the
inline code can be exercised without running a cycle; when the checkout has `stress_summary`, that is probed too."""
import itertools
import math
import random
import statistics
import sys

sys.path.insert(0, sys.argv[1])
from greg.cognition import evolution as E  # noqa: E402

inf, nan = math.inf, math.nan


def inline(inc_s, cand_s):
    adversarial = {}
    for kind in sorted({k.split(":")[0] for k in inc_s}):
        ki = [inc_s[k] for k in inc_s if k.startswith(kind)]
        kc = [cand_s[k] for k in cand_s if k.startswith(kind)]
        adversarial[kind] = {"incumbent": round(statistics.fmean(ki), 6), "candidate": round(statistics.fmean(kc), 6)}
        if any(math.isinf(v) for v in ki + kc):
            finite = [(a, b) for a, b in zip(ki, kc) if not (math.isinf(a) or math.isinf(b))]
            adversarial[kind]["wrong"] = {"incumbent": sum(map(math.isinf, ki)), "candidate": sum(map(math.isinf, kc)),
                                          "both_answered": len(finite),
                                          "incumbent_answered_mean": round(statistics.fmean(a for a, _ in finite), 6)
                                          if finite else None,
                                          "candidate_answered_mean": round(statistics.fmean(b for _, b in finite), 6)
                                          if finite else None}
    return adversarial


summary = getattr(E, "stress_summary", None) or inline


def gate(inc_s, cand_s, agg=None):
    try:
        adv = (agg or summary)(inc_s, cand_s)
        return {k: E.stress_worsened(v) for k, v in adv.items()}
    except Exception as exc:                      # noqa: BLE001
        return f"RAISES {type(exc).__name__}: {exc}"


def show(name, inc, cand, agg=None):
    print(f"{name:58s} -> {gate(inc, cand, agg)}")


print("checkout:", sys.argv[1], "| aggregation:", "stress_summary" if summary is not inline else "inline (239a87f)")
print("-- semantics: wrong (inf) vs abstention (finite) vs finite loss")
show("1 inc 1 wrong, cand abstains on EVERY item (CR abstain=1.0)",
     {"lean:a": inf, "lean:b": 0.01, "lean:c": 0.01}, {"lean:a": 1.0, "lean:b": 1.0, "lean:c": 1.0})
show("2 equal wrong (1-1), answered 10x worse", {"k:a": inf, "k:b": 0.01, "k:c": 0.01},
     {"k:a": inf, "k:b": 0.1, "k:c": 0.1})
show("3 fewer wrong (2->1), answered 10x worse", {"k:a": inf, "k:b": inf, "k:c": 0.01},
     {"k:a": inf, "k:b": 0.1, "k:c": 0.1})
show("4 more wrong (1->2), answered better", {"k:a": inf, "k:b": 0.1, "k:c": 0.1},
     {"k:a": inf, "k:b": inf, "k:c": 0.01})
show("5 equal wrong on DISJOINT items, both_answered == 0", {"k:a": inf, "k:b": 0.01}, {"k:a": 5.0, "k:b": inf})
show("6 equal wrong on disjoint items, rest equal", {"k:a": inf, "k:b": 0.01, "k:c": 0.01},
     {"k:a": 9.0, "k:b": inf, "k:c": 0.01})
print("-- nonfinite / malformed")
show("7 NaN candidate item among finite", {"k:a": 0.01, "k:b": 0.01}, {"k:a": nan, "k:b": 0.01})
show("8 NaN incumbent item among finite", {"k:a": nan, "k:b": 0.01}, {"k:a": 9.0, "k:b": 9.0})
show("9 -inf incumbent item (counted as a 'wrong' answer)", {"k:a": -inf, "k:b": 0.01}, {"k:a": 0.5, "k:b": 0.5})
show("10 -inf candidate item", {"k:a": 0.01, "k:b": 0.01}, {"k:a": -inf, "k:b": 0.01})
show("11 +inf and -inf in one set (mean NaN)", {"k:a": inf, "k:b": -inf}, {"k:a": 0.5, "k:b": 0.5})
for name, kind in (("12 stress_worsened, NaN means", {"incumbent": 0.01, "candidate": nan}),
                   ("13 stress_worsened, incumbent -inf mean", {"incumbent": -inf, "candidate": 5.0}),
                   ("14 stress_worsened, malformed counts (str)", {"incumbent": inf, "candidate": inf,
                    "wrong": {"incumbent": "1", "candidate": "2", "both_answered": 3,
                              "incumbent_answered_mean": 0.1, "candidate_answered_mean": 0.1}}),
                   ("15 stress_worsened, both_answered>0 but means None", {"incumbent": inf, "candidate": inf,
                    "wrong": {"incumbent": 1, "candidate": 1, "both_answered": 3,
                              "incumbent_answered_mean": None, "candidate_answered_mean": None}}),
                   ("16 stress_worsened, NaN answered means", {"incumbent": inf, "candidate": inf,
                    "wrong": {"incumbent": 1, "candidate": 1, "both_answered": 3,
                              "incumbent_answered_mean": 0.1, "candidate_answered_mean": nan}}),
                   ("17 stress_worsened, negative counts", {"incumbent": inf, "candidate": inf,
                    "wrong": {"incumbent": 1, "candidate": -5, "both_answered": 3,
                              "incumbent_answered_mean": 0.1, "candidate_answered_mean": 0.1}})):
    try:
        print(f"{name:58s} -> {E.stress_worsened(kind)}")
    except Exception as exc:  # noqa: BLE001
        print(f"{name:58s} -> RAISES {type(exc).__name__}: {exc}")
print("-- alignment")
show("18 kinds 'lean','leaner': lean 50x worse is masked", {"lean:a": 0.01, "leaner:a": 10.0},
     {"lean:a": 0.5, "leaner:a": 0.0})
show("19 other key order: c 50x worse, by key = worsened",
     {"k:a": inf, "k:b": 0.01, "k:c": 0.01}, {"k:c": 0.5, "k:b": 0.01, "k:a": inf})
show("20 candidate missing a key", {"k:a": inf, "k:b": 0.01, "k:c": 0.01}, {"k:a": inf, "k:b": 0.01})
print("-- rounding")
show("21 answered means 4e-7 vs 4.9e-7 (+22%) round to 0.0", {"k:a": inf, "k:b": 4e-7}, {"k:a": inf, "k:b": 4.9e-7})
show("22 finite means 4e-7 vs 4.9e-7 (+22%), old path", {"k:a": 4e-7}, {"k:a": 4.9e-7})

print("-- monotonicity: well-formed random sets, new gate rejects every set the old gate rejects")
rng = random.Random(0)
diff = {"old_reject_new_pass": 0, "old_pass_new_reject": 0, "same": 0}
for _ in range(20000):
    n = rng.randint(1, 6)
    inc = {f"k:{i}": (inf if rng.random() < 0.25 else rng.choice([0.0, 0.01, 0.0105, 0.02, 1.0])) for i in range(n)}
    cand = {f"k:{i}": (inf if rng.random() < 0.25 else rng.choice([0.0, 0.01, 0.0105, 0.02, 1.0])) for i in range(n)}
    adv = summary(inc, cand)["k"]
    old = E.worsened(adv["incumbent"], adv["candidate"])
    new = E.stress_worsened(adv)
    diff["same" if old == new else "old_reject_new_pass" if old else "old_pass_new_reject"] += 1
print(diff)
