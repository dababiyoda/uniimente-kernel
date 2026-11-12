"""Design pilot, family C (dev seeds 0-9, scratch namespace; NOT the experiment's generator)."""
import math, random
import numpy as np
from greg.cognition.genomes import library
from greg.cognition.genomes import solvers_c as S

def run(d):
    return library.run("causal_backdoor", d, {"latency_limit": 10})
def decide(out):
    o = out["output"]
    if not o: return "ABSTAIN"
    lo, hi = o["ate"] - 1.96 * o["se"], o["ate"] + 1.96 * o["se"]
    return "TREAT" if lo > 0 else "DO_NOT_TREAT" if hi < 0 else "UNDECIDED"
DEC = ("TREAT", "DO_NOT_TREAT")

def gen(seed, kind):
    r = random.Random(f"repr-design-probe:pilot-c:{seed}:{kind}")
    n = r.choice((400, 800, 1500)); eff = r.choice((-1, 1)) * r.uniform(0.5, 1.2)
    cols = {"Z": [], "T": [], "Y": [], "W": []}
    tau = int(n * (0.5 if kind == "drift" else 0.85))
    nodes = [{"name": "Z", "type": "binary"}, {"name": "T", "type": "binary"}, {"name": "Y", "type": "continuous"},
             {"name": "W", "type": "continuous"}]
    edges = [["Z", "Y"], ["T", "Y"], ["W", "Y"]]; adj = []
    if kind == "m_structure":
        nodes = [{"name": "U1", "type": "continuous", "observed": False}, {"name": "U2", "type": "continuous", "observed": False},
                 {"name": "Z", "type": "continuous"}, {"name": "T", "type": "binary"}, {"name": "Y", "type": "continuous"}]
        edges = [["U1", "Z"], ["U2", "Z"], ["U1", "T"], ["U2", "Y"], ["T", "Y"]]; cols = {"Z": [], "T": [], "Y": []}
    for i in range(n):
        z = int(r.random() < 0.5); w = r.gauss(0, 1)
        if kind == "m_structure":
            u1, u2 = r.gauss(0, 1), r.gauss(0, 1)
            t = int(r.random() < 1 / (1 + math.exp(-1.5 * u1))); y = eff * t + 1.5 * u2 + r.gauss(0, 1)
            cols["Z"].append(round(u1 + u2 + r.gauss(0, .5), 6)); cols["T"].append(t); cols["Y"].append(round(y, 6)); continue
        if kind in ("missing_edge", "clean_confounded"):
            s = 1 if r.random() < 0.7 else -1                     # confounding against (reversal) or with the effect
            if i == 0: sgn = s
            pt = 0.85 if (z == 1) == (eff * sgn > 0) else 0.15
            t = int(r.random() < pt); y = eff * t - sgn * 3.0 * eff * z + 0.5 * w + r.gauss(0, 1)
        elif kind in ("drift", "drift_recent"):
            t = int(r.random() < 0.5); e = eff if i >= tau else -1.5 * eff; y = e * t + 0.8 * z + 0.5 * w + r.gauss(0, 1)
        else:
            t = int(r.random() < 0.5); y = eff * t + 0.8 * z + 0.5 * w + r.gauss(0, 1)
        cols["Z"].append(z); cols["T"].append(t); cols["Y"].append(round(y, 6)); cols["W"].append(round(w, 6))
    if kind == "clean_confounded": edges.append(["Z", "T"]); adj = ["Z"]
    return {"nodes": nodes, "edges": edges, "treatment": "T", "outcome": "Y", "adjustment_set": adj, "samples": cols}, eff

def general(d):
    g = S._ca(d); desc = S._descendants(g["children"], g["t"])
    extra = [v for v in g["info"] if v not in (g["t"], g["y"]) and v not in desc and g["info"][v]["observed"] and v in g["cols"]]
    return {**d, "adjustment_set": sorted(set(d["adjustment_set"]) | set(extra))}
def failed_independencies(d):
    g = S._ca(d); z = set(g["z"]); bad = []
    for v in g["info"]:
        if v in (g["t"], g["y"]) or v in z or not g["info"][v]["observed"] or v not in g["cols"]: continue
        if S._dsep_moral(g["parents"], {v}, {g["t"]}, z) and not z:        # pilot: unconditional case only
            t = np.asarray(g["cols"][g["t"]]); x = np.asarray(g["cols"][v], dtype=float); a, b = x[t == 1], x[t == 0]
            zs = (a.mean() - b.mean()) / math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            if abs(zs) > 3.29: bad.append(v)
    return bad
def half(d, lo, hi): return {**d, "samples": {k: v[lo:hi] for k, v in d["samples"].items()}}
def opposite(a, b): return a in DEC and b in DEC and a != b

def arms(d):
    n = len(d["samples"]["T"]); r0 = decide(run(d)); r1 = decide(run(general(d)))
    rE, rL = decide(run(half(d, 0, n // 2))), decide(run(half(d, n // 2, n)))
    recs = [x for x in (r0, r1, rL) if x != "ABSTAIN"]
    cons = recs[0] if len(set(recs)) == 1 else "UNDECIDED"
    bad = failed_independencies(d); cF = r1 != "ABSTAIN" and r0 != r1 and (r0 in DEC or r1 in DEC); cT = opposite(rE, rL)
    if bad and cT: cause, final = ["formalization", "environmental_change"], "UNDECIDED"
    elif bad: cause, final = ["formalization"], r1
    elif cT: cause, final = ["environmental_change"], rL
    elif cF: cause, final = ["assumption", "formalization"], "UNDECIDED"
    else: cause, final = [], r0
    return {"R0": r0, "general": r1, "late_half": rL, "conservative": cons, "repair": final}, cause

def grade(rec, eff): return "ok" if rec == ("TREAT" if eff > 0 else "DO_NOT_TREAT") else "wrong" if rec in DEC else "none"
tot = {}
for kind in ("clean_unconfounded", "clean_confounded", "m_structure", "missing_edge", "drift", "drift_recent"):
    tab = {}; causes = {}
    for seed in range(10):
        d, eff = gen(seed, kind); out, cause = arms(d)
        for k, rec in out.items():
            g_ = grade(rec, eff); tab.setdefault(k, {"ok": 0, "none": 0, "wrong": 0})[g_] += 1
            tot.setdefault(k, {"ok": 0, "none": 0, "wrong": 0})[g_] += 1
        causes[tuple(cause)] = causes.get(tuple(cause), 0) + 1
    print(f"{kind:19s}", {k: f"{v['ok']}/{v['none']}/{v['wrong']}" for k, v in tab.items()}, "| causes", causes)
print("TOTAL ok/none/wrong (60 dev items)", {k: f"{v['ok']}/{v['none']}/{v['wrong']}" for k, v in tot.items()})
