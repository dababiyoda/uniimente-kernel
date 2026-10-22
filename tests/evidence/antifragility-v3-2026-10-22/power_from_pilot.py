"""Power of a paired per-cell rule on the stress, from the disclosed pilot's HIGH pass rates (seeds 0-5).
Rule: after the incumbent's first verified failure in the cell, every later stress mission in that cell also runs the
next attached fit in shadow; prefer the alternative when a one-sided exact sign test on discordant pairs gives p<alpha.
Pairs are simulated independent given the function (no pilot data on within-instance correlation)."""
import random, math
FUN = ("sphere", "ackley", "griewank", "rosenbrock", "rastrigin")
P_SW = {"sphere": 1/6, "ackley": 2/6, "griewank": 2/6, "rosenbrock": 3/6, "rastrigin": 2/6}
P_MS = {"sphere": 6/6, "ackley": 0/6, "griewank": 6/6, "rosenbrock": 6/6, "rastrigin": 2/6}
def p_sign(w, l):
    n = w + l
    return 1.0 if n == 0 else sum(math.comb(n, i) for i in range(w, n + 1)) / 2 ** n
def sim(n_missions, alpha=0.05, shadow_all=False, reps=20000, rnd=random.Random(7)):
    hit = 0
    for _ in range(reps):
        failed, w, l = shadow_all, 0, 0
        for i in range(n_missions):
            f = FUN[i % 5]
            a = rnd.random() < P_SW[f]; b = rnd.random() < P_MS[f]
            if failed:
                w += (b and not a); l += (a and not b)
            if not a: failed = True
        hit += p_sign(w, l) < alpha
    return hit / reps
for n in (12, 24, 36, 60):
    print(n, "failure-triggered:", round(sim(n), 3), " shadow-from-start:", round(sim(n, shadow_all=True), 3))
