"""Layer 2 crowd intelligence: the one-step agreement-weighted vote (an acquisition target handed over by #179).

On #179's sparse multi-class crowds Dawid-Skene EM lost to a one-step weighted vote (8/32, p = 9e-5;
``greg/path.json`` on #179 at d0c2733e: "the one-step vote is the acquisition target"). This module makes that vote
an executable genome on GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker ->
independent verifier -> CognitiveReceipt), registered and withheld like every non-seed family.

* ``crowd_weighted_vote`` (``weighted_vote_labels``): (1) plurality label per item; (2) each worker's accuracy
  estimated as its leave-one-out agreement with the other workers' plurality on the items it labelled, Laplace
  smoothed; (3) Nitzan-Paroush weights ``log((k - 1) p / (1 - p))``; (4) the weighted plurality per item. Verified by
  an independent recomputation (a different code path over a transposed index) of every weight and label.

Baseline: plurality vote. Competitor: Dawid-Skene EM (#179's ``crowd`` family mechanism, ported here with its
smoothing, initialisation and stopping rule; #179's code is not on this branch).

Everything is read-only computation; no output creates authority.
"""
from __future__ import annotations

import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4",
           "#179 acquisition target: pr155-crowd-sparse (Dawid-Skene lost to the one-step weighted vote, 8/32)")
NAME_MAX = 64
MAX_ITEMS, MAX_WORKERS, MAX_VOTES, MAX_CLASSES = 20000, 5000, 200000, 50
P_CLIP = (0.01, 0.99)


def _votes(data):
    """({item: {worker: label}}, classes) validated."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    k = bounded_int(data.get("num_classes"), low=2, high=MAX_CLASSES, name="num_classes")
    votes = data.get("crowd_votes")
    if not isinstance(votes, dict) or not 1 <= len(votes) <= MAX_ITEMS:
        raise GenomeError(f"crowd_votes: {{item: {{worker: label}}}} with 1-{MAX_ITEMS} items")
    workers, total = set(), 0
    for item, row in votes.items():
        if not isinstance(item, str) or not 0 < len(item) <= NAME_MAX or not isinstance(row, dict) or not row:
            raise GenomeError("each item: a name of 1-64 characters with at least one vote")
        for w, label in row.items():
            if not isinstance(w, str) or not 0 < len(w) <= NAME_MAX or type(label) is not int or not 0 <= label < k:
                raise GenomeError("each vote: worker name -> label in 0..num_classes-1")
            workers.add(w)
        total += len(row)
    if len(workers) > MAX_WORKERS or total > MAX_VOTES:
        raise GenomeError(f"at most {MAX_WORKERS} workers and {MAX_VOTES} votes")
    return votes, k


def _plurality(counts):
    """Index of the largest value; ties to the smallest label."""
    best = 0
    for c in range(1, len(counts)):
        if counts[c] > counts[best]:
            best = c
    return best


def _weight(p, k):
    p = min(max(p, P_CLIP[0]), P_CLIP[1])
    return math.log((k - 1) * p / (1 - p))


def weighted_vote(votes, k):
    """Solver path: (labels, weights)."""
    tallies = {}
    for item, row in votes.items():
        t = [0] * k
        for label in row.values():
            t[label] += 1
        tallies[item] = t
    agree, seen = {}, {}
    for item, row in votes.items():
        for w, label in row.items():
            others = list(tallies[item])
            others[label] -= 1
            if sum(others) == 0 or sorted(others)[-1] == sorted(others)[-2]:
                continue                                  # no other vote, or the others tie: uninformative
            seen[w] = seen.get(w, 0) + 1
            agree[w] = agree.get(w, 0) + (label == _plurality(others))
    weights = {}
    for row in votes.values():
        for w in row:
            if w not in weights:
                weights[w] = _weight((agree.get(w, 0) + 1) / (seen.get(w, 0) + 2), k)
    labels = {}
    for item, row in votes.items():
        score = [math.fsum(weights[w] for w, label in row.items() if label == c) for c in range(k)]
        labels[item] = _plurality(score)
    return labels, weights


def vote_solve(data, budget):
    votes, k = _votes(data)
    labels, weights = weighted_vote(votes, k)
    return answer({"labels": labels, "worker_weights": weights},
                  {"method": "one-step agreement-weighted vote: leave-one-out plurality agreement, Laplace "
                             "smoothing, Nitzan-Paroush log-odds weights", "items": len(votes),
                   "workers": len(weights), "classes": k, "probability_clip": list(P_CLIP)})


def _independent(votes, k):
    """Verifier path, written apart from the solver: a worker-major index, counts per (item, label), and the same
    estimator definitions recomputed."""
    by_worker = {}
    count = {}
    for item, row in votes.items():
        for w, label in row.items():
            by_worker.setdefault(w, []).append((item, label))
            count[item, label] = count.get((item, label), 0) + 1
    weights = {}
    for w, pairs in by_worker.items():
        hits = trials = 0
        for item, label in pairs:
            rest = [count.get((item, c), 0) - (c == label) for c in range(k)]
            top = max(rest)
            if top == 0 or rest.count(top) > 1:
                continue
            trials += 1
            hits += rest.index(top) == label
        p = (hits + 1) / (trials + 2)
        p = min(max(p, P_CLIP[0]), P_CLIP[1])
        weights[w] = math.log((k - 1) * p / (1 - p))
    labels = {}
    for item, row in votes.items():
        score = [math.fsum(weights[w] for w, label in row.items() if label == c) for c in range(k)]
        labels[item] = score.index(max(score))           # exact (fsum is correctly rounded); ties to the smallest
    return labels, weights


def vote_verify(data, output, certificate):
    votes, k = _votes(data)
    if (not isinstance(output, dict) or set(output) != {"labels", "worker_weights"}
            or not isinstance(output["labels"], dict) or not isinstance(output["worker_weights"], dict)):
        return {"output_shape": False}
    labels, weights = _independent(votes, k)
    claimed_w = output["worker_weights"]
    return {"output_shape": True,
            "weights_recomputed": set(claimed_w) == set(weights) and all(
                type(claimed_w[w]) in (int, float) and math.isfinite(claimed_w[w])
                and abs(claimed_w[w] - weights[w]) <= 1e-9 for w in weights),
            "labels_recomputed": output["labels"] == labels and all(type(v) is int for v in output["labels"].values())}


def vote_instance(seed):
    """Simulated crowds: reliable, mediocre, spamming and adversarial workers with heavy-tailed activity; sparse
    (3 votes per item) or dense (7-15 votes per item) redundancy."""
    r = random.Random(f"genome:crowd_weighted_vote:{seed}")
    sparse = seed % 2 == 0
    k = r.choice((2, 3, 4, 5))
    items = r.randint(200, 500)
    n_workers = r.randint(30, 100)
    kinds = r.choices(("reliable", "mediocre", "spammer", "adversary"), weights=(0.45, 0.3, 0.2, 0.05),
                      k=n_workers)
    acc = []
    for kind in kinds:
        if kind == "reliable":
            acc.append(r.uniform(0.75, 0.95))
        elif kind == "mediocre":
            acc.append(r.uniform(1 / k + 0.05, 0.75))
        elif kind == "spammer":
            acc.append(1 / k)
        else:
            acc.append(r.uniform(0.0, 1 / k * 0.5))
    activity = [r.paretovariate(1.2) for _ in range(n_workers)]
    truth = [r.randrange(k) for _ in range(items)]
    votes = {}
    for i in range(items):
        m = 3 if sparse else r.randint(7, 15)
        chosen = set()
        while len(chosen) < min(m, n_workers):
            chosen.add(r.choices(range(n_workers), weights=activity)[0])
        row = {}
        for w in sorted(chosen):
            if r.random() < acc[w]:
                row[f"w{w:03d}"] = truth[i]
            else:
                row[f"w{w:03d}"] = r.choice([c for c in range(k) if c != truth[i]])
        votes[f"i{i:04d}"] = row
    return {"crowd_votes": votes, "num_classes": k}, {"labels": {f"i{i:04d}": t for i, t in enumerate(truth)}}


def vote_subregion(data):
    votes, k = _votes(data)
    mean = sum(len(r) for r in votes.values()) / len(votes)
    return ("sparse" if mean <= 4 else "dense") + ("_binary" if k == 2 else "_multiclass")


def vote_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("labels"), dict):
        return {"quality": -1.0, "category": "abstain"}
    labels = output["labels"]
    if set(labels) != set(truth["labels"]):
        return {"quality": -2.0, "category": "wrong"}
    hits = sum(1 for i, t in truth["labels"].items() if labels[i] == t)
    return {"quality": hits / len(truth["labels"]), "category": "correct"}


def vote_plurality(data):
    """Baseline: unweighted plurality vote (ties to the smallest label)."""
    votes, k = _votes(data)
    out = {}
    for item, row in votes.items():
        t = [0] * k
        for label in row.values():
            t[label] += 1
        out[item] = _plurality(t)
    return {"labels": out}


def vote_dawid_skene(data, iterations=50, smoothing=1.0):
    """Competitor: Dawid-Skene EM as in #179's ``crowd`` family (repertoire.crowd_label at d0c2733e): soft-plurality
    initialisation, Dirichlet smoothing 1.0, log-space E-step, stop when the MAP objective changes by < 1e-7 or after
    50 sweeps. Per-worker confusion matrices (each worker is its own independence group here)."""
    votes, k = _votes(data)
    items = sorted(votes)
    workers = sorted({w for row in votes.values() for w in row})
    post = {i: [sum(1 for g in votes[i].values() if g == c) / len(votes[i]) for c in range(k)] for i in items}
    previous = None
    for _ in range(iterations):
        prior = [(sum(post[i][c] for i in items) + smoothing) / (len(items) + k * smoothing) for c in range(k)]
        counts = {g: [[smoothing] * k for _ in range(k)] for g in workers}
        for i in items:
            for g, label in votes[i].items():
                for c in range(k):
                    counts[g][c][label] += post[i][c]
        confusion = {g: [[x / sum(row) for x in row] for row in rows] for g, rows in counts.items()}
        likelihood = 0.0
        for i in items:
            logs = [math.log(prior[c]) + sum(math.log(confusion[g][c][label]) for g, label in votes[i].items())
                    for c in range(k)]
            top = max(logs)
            total = sum(math.exp(x - top) for x in logs)
            post[i] = [math.exp(x - top) / total for x in logs]
            likelihood += top + math.log(total)
        objective = likelihood + smoothing * (sum(math.log(p) for p in prior) + sum(
            math.log(x) for rows in confusion.values() for row in rows for x in row))
        if previous is not None and abs(objective - previous) < 1e-7:
            break
        previous = objective
    return {"labels": {i: max(range(k), key=lambda c: (post[i][c], -c)) for i in items}}


_DEV = "development seeds 0-9 only (admission --dev; not admission evidence): "

INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="collective.crowd.weighted_vote", version="1.0.0", family="crowd_weighted_vote", layer=2,
            operation="weighted_vote_labels", epistemic_class="estimate",
            subgeometry="labels for items from many workers of unknown, unequal reliability; sparse redundancy "
                        "(about three votes per item) where per-worker confusion matrices are poorly identified",
            source_provenance="Nitzan and Paroush (1982) optimal weighted majority; Karger, Oh and Shah (2011) "
                              "one-step weighting; #179 acquisition target (pr155-crowd-sparse)",
            native_representation="{item: {worker: label}} and the number of classes",
            required_inputs=("crowd_votes", "num_classes"),
            output_contract={"labels": "{item: label}", "worker_weights": "{worker: log-odds weight}"},
            algorithm_or_runtime="plurality; leave-one-out agreement per worker with Laplace smoothing; "
                                 "log((k - 1) p / (1 - p)) weights; weighted plurality (one step, no iteration)",
            parameters={"probability_clip": list(P_CLIP), "laplace": "(agree + 1) / (trials + 2)"},
            composition_inputs=("votes from observers, sources or reviewers",),
            composition_outputs=("labels", "worker weights (reliability estimates)"),
            evidence_type="collective_trace",
            verification_method="every worker weight and every label recomputed by an independent implementation "
                                "over a worker-major index (exact match of labels, weights within 1e-9)",
            confidence_semantics="the labels the declared estimator gives; weights estimate worker reliability under "
                                 "independent errors; not a posterior probability of each label",
            resource_profile="O(votes x classes)", latency_profile="milliseconds at benchmark size",
            known_strengths=("robust on sparse crowds where EM's per-worker confusion matrices overfit",
                             "down-weights spammers and inverts systematic adversaries",
                             "deterministic, one pass, fully recomputable"),
            known_failure_modes=("assumes workers err independently; colluding workers get high weights",
                                 "a symmetric (single-accuracy) worker model: class-dependent confusion is not modelled",
                                 "the first-step plurality anchors the weights: a majority of bad workers inverts it"),
            counterindications=("dense crowds with class-dependent errors (Dawid-Skene can model the confusion)",
                                "correlated or colluding sources", "few items per worker (weights stay near the "
                                "prior)"),
            abstention_conditions=("none: every item with a vote gets a label (an item whose votes tie goes to the "
                                   "smallest label)",),
            benchmark_suite="simulated crowds of 30-100 workers (45% reliable, 30% mediocre, 20% spammers, 5% "
                            "adversaries) with Pareto activity over 200-500 items and 2-5 classes; even seeds sparse "
                            "(3 votes per item), odd seeds dense (7-15); quality is accuracy against the simulated "
                            "truth; seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="plurality vote",
            competitor="Dawid-Skene EM with per-worker confusion matrices (#179's crowd mechanism, ported)",
            buildability="BUILDABLE_NOW", memory_model="stateless",
            learning_rule="weights re-estimated from each request's votes; nothing persists", lineage=LINEAGE),
        solve=vote_solve, verify=vote_verify, instance=vote_instance, score=vote_score,
        baseline=vote_plurality, competitor=vote_dawid_skene, subregion=vote_subregion, tolerance=1e-9),
]
