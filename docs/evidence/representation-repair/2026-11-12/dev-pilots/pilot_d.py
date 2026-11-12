"""Design pilot, family D (dev seeds 0-9, scratch namespace 'repr-design-probe'; NOT the experiment's generator)."""
import math, random
from statistics import NormalDist
from greg.cognition.genomes import library
from greg.cognition.genomes.control_b import _cu_loss

CRIT = NormalDist().inv_cdf(1 - 0.001 / 2)
def run(d):
    return library.run("basal_cusum_detect", d, {"latency_limit": 5})
def alarm(d):
    return run(d)["output"]["alarm"]

def gen(seed, kind):
    r = random.Random(f"repr-design-probe:pilot-d:{seed}:{kind}")
    T = r.randrange(240, 601); sigma = round(r.uniform(0.5, 3.0), 4); mu = round(r.uniform(-5, 5), 4)
    delta = round(sigma * r.choice((0.75, 1.0, 1.5)), 6); n0 = max(30, T // 8)
    s = [mu + sigma * r.gauss(0, 1) for _ in range(T)]; tau = None; decl = mu
    sh = delta * r.choice((1.0, 2.0)) * r.choice((-1, 1))
    if kind in ("change", "stale_change"): tau = r.randrange(T // 3, (3 * T) // 4)
    if kind == "early_change": tau = r.randrange(n0 // 2, n0)
    if tau is not None: s = [x + (sh if t >= tau else 0) for t, x in enumerate(s)]
    if kind in ("stale", "stale_change"): decl = round(mu - delta * r.choice((1.0, 1.5)) * r.choice((-1, 1)), 4)
    if kind == "spike":
        j = r.randrange(T // 3, (3 * T) // 4); s[j] += r.choice((-1, 1)) * r.uniform(7, 10) * sigma
    if kind == "variance_shift":   # unplanned-for fault: no declared check covers it
        j = r.randrange(T // 3, (3 * T) // 4); s = [mu + (x - mu) * (2.0 if t >= j else 1.0) for t, x in enumerate(s)]
    return {"stream": [round(x, 6) for x in s], "mu0": decl, "sigma": sigma, "delta": delta, "arl0": 5000.0}, tau, n0

def self_start(d, n0):
    pre = d["stream"][:n0]; m = sum(pre) / n0; sd = (sum((x - m) ** 2 for x in pre) / (n0 - 1)) ** .5
    return {**d, "stream": d["stream"][n0:], "mu0": round(m, 6), "sigma": round(sd, 6), "delta": round(d["delta"] / d["sigma"] * sd, 6)}
def a1(d, lo, hi):
    seg = d["stream"][lo:hi]; return abs((sum(seg) / len(seg) - d["mu0"]) * math.sqrt(len(seg)) / d["sigma"]) <= CRIT
def W(d):
    c = run(d)["proof"]["certificate"]; return max(10, math.ceil(c["h"] / c["k"]))
def conflict(a, b, w): return (a is None) != (b is None) or (a is not None and abs(a - b) > w)

def arms(d, n0):
    w = W(d); a0 = alarm(d); a1_ = alarm(self_start(d, n0)); a1_ = None if a1_ is None else a1_ + n0
    clip = {**d, "stream": [min(max(x, d["mu0"] - 4 * d["sigma"]), d["mu0"] + 4 * d["sigma"]) for x in d["stream"]]}
    ac = alarm(clip)
    AND = None if a0 is None or a1_ is None else max(a0, a1_)
    OR = min([x for x in (a0, a1_) if x is not None], default=None)
    robust = None if ac is None or a1_ is None else max(ac, a1_)
    # --- repair
    cause, final = [], a0
    drop = None
    if a0 is not None:           # drop-one on the alarm window: exactly one reading whose removal removes the alarm
        hits = []
        for j in range(max(0, a0 - 8), a0 + 1):
            dj = {**d, "stream": d["stream"][:j] + d["stream"][j + 1:]}
            aj = alarm(dj)
            if aj is None or aj > a0 + w: hits.append(j)
        if len(hits) == 1: drop = hits[0]
    if drop is not None:
        cause = ["observation"]; final = alarm({**d, "stream": d["stream"][:drop] + d["stream"][drop + 1:]})
        if final is not None and final >= drop: final += 1
    elif conflict(a0, a1_, w):
        h = n0 // 2; e, l = a1(d, 0, h), a1(d, h, n0)
        if not e and not l: cause = ["assumption"]; final = a1_
        elif e and not l: cause = ["environmental_change"]; final = a0
        elif not e and l: cause = ["assumption", "observation"]; final = a0
        else: cause = ["assumption", "formalization"]; final = a0       # conflict, no declared check fails: unseparated
    return {"R0": a0, "R1": a1_, "AND": AND, "OR": OR, "robustAND": robust, "repair": final}, cause

tot = {}
for kind in ("quiet", "change", "stale", "stale_change", "spike", "early_change", "variance_shift"):
    loss = {}; causes = {}
    for seed in range(10):
        d, tau, n0 = gen(seed, kind); out, cause = arms(d, n0)
        for k, a in out.items():
            l, cat = _cu_loss(len(d["stream"]), tau, a); loss[k] = loss.get(k, 0) + l; tot[k] = tot.get(k, 0) + l
        causes[tuple(cause)] = causes.get(tuple(cause), 0) + 1
    print(f"{kind:15s}", {k: round(v) for k, v in loss.items()}, "| causes", causes)
print("TOTAL (70 dev items)", {k: round(v) for k, v in tot.items()})
