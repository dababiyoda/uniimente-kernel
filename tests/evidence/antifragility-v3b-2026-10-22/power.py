"""v3b power, declared before the freeze. Per-mission discordant rates per HIGH objective are v3's stress pairs
(hypothesis-generating data, tests/evidence/antifragility-v3-2026-10-22/README.md), Laplace-smoothed. The holdout
is simulated from the same rates: 10 HIGH instances per objective. Rules are v3's: per-cell one-sided exact sign
test, p < 0.05 with >= 5 discordant pairs; GAIN needs LEARN vs CONTROL holdout sign test p < 0.05 and no cell below
PRE (a fired cell where the alternative loses more than it wins counts as a regression)."""
import random
from math import comb

V3 = {"rosenbrock": (6, 0, 7), "griewank": (3, 0, 7), "sphere": (1, 0, 7), "rastrigin": (1, 2, 7), "ackley": (0, 4, 6)}


def p_one(w, l):
    n = w + l
    return 1.0 if n == 0 else sum(comb(n, i) for i in range(w, n + 1)) / 2 ** n


def rates(a, i, n):                      # Laplace: (a+1)/(n+3), (i+1)/(n+3)
    return (a + 1) / (n + 3), (i + 1) / (n + 3)


def sim(per_objective, holdout=10, trials=4000, rnd=random.Random(20261022)):
    fire = {k: 0 for k in V3}
    gain = 0
    for _ in range(trials):
        fired = {}
        for f, (a, i, n) in V3.items():
            pa, pi = rates(a, i, n)
            w = l = 0
            hit = False
            for _ in range(per_objective - 1):           # the first failure in a cell only triggers
                u = rnd.random()
                w += u < pa
                l += pa <= u < pa + pi
                if w + l >= 5 and p_one(w, l) < 0.05:
                    hit = True
                    break
            fired[f] = hit
            fire[f] += hit
        W = L = 0
        regress = False
        for f, hit in fired.items():
            if not hit:
                continue
            pa, pi = rates(*V3[f])
            wf = sum(rnd.random() < pa for _ in range(holdout))
            lf = sum(rnd.random() < pi for _ in range(holdout))
            W, L = W + wf, L + lf
            regress |= lf > wf
        gain += (W + L >= 1 and p_one(W, L) < 0.05 and not regress)
    return {k: round(v / trials, 3) for k, v in fire.items()}, round(gain / trials, 3)


if __name__ == "__main__":
    for n in (8, 12, 16, 20, 24):
        f, g = sim(n)
        print(f"{n:3d} stress missions per HIGH objective: P(fire) {f}  P(GAIN-shaped holdout) {g}")
