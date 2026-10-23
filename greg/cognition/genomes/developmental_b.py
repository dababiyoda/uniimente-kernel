"""Layer 4 developmental intelligence, batch B: graph diffusion (harmonic label propagation by local averaging).

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``) lists "graph diffusion" as ABSENT
from Layer 4 ("no graph-diffusion family; cross_substrate backcast proposes one"). Effect, not metaphor: the effect
sought is that a few verified facts spread to the parts of a structure they bear on, by purely local exchanges, until
every unit agrees with its neighbourhood (a shared target state). The mechanism is harmonic label propagation (Zhu,
Ghahramani and Lafferty 2003): verified nodes are clamped, and every other node repeatedly takes the weighted average
of its neighbours' class scores until the residual vanishes. The fixed point is the unique harmonic function, i.e. the
probability that a random walk from the node first reaches a seed of each class.

* ``develop_diffusion`` (``propagate_graph_labels``): label the nodes of an undirected weighted graph (claims linked
  by support, services linked by dependency) from a few verified seed labels. Verified by an independent direct
  solve of the harmonic linear system (NumPy) per connected component: the claimed scores must match it, labels must
  be its argmax (ties within tolerance accepted either way), and nodes with no seed in their component must abstain.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 and this lane's declared review range 9400-9439 only.
"""
from __future__ import annotations

import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md (Layer 4 ABSENT: graph diffusion)")
GD_MAX_NODES, GD_MAX_EDGES, GD_MAX_CLASSES = 400, 8000, 10
GD_TOL = 1e-11                   # stop when no score moves by more than this in one sweep
GD_MAX_SWEEPS = 200_000
GD_SCORE_TOL = 1e-6              # verifier: claimed scores against the direct solve
GD_TIE = 1e-7                    # verifier: classes within this of the top are ties


def _input(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    edges, seeds = data.get("graph_edges"), data.get("seed_labels")
    k = bounded_int(data.get("num_label_classes"), low=2, high=GD_MAX_CLASSES, name="num_label_classes")
    if not isinstance(edges, list) or not 1 <= len(edges) <= GD_MAX_EDGES:
        raise GenomeError(f"graph_edges: 1-{GD_MAX_EDGES} [u, v, weight] triples")
    weights = {}
    for e in edges:
        if (not isinstance(e, list) or len(e) != 3 or not all(isinstance(x, str) and 1 <= len(x) <= 64
                                                                for x in e[:2]) or e[0] == e[1]):
            raise GenomeError("edge: [node, other node, weight] with distinct string names")
        w = finite(e[2], low=1e-9, high=1e9, name="edge weight")
        key = tuple(sorted(e[:2]))
        if key in weights:
            raise GenomeError("duplicate edge")
        weights[key] = w
    nodes = sorted({x for key in weights for x in key})
    if len(nodes) > GD_MAX_NODES:
        raise GenomeError(f"more than {GD_MAX_NODES} nodes")
    if not isinstance(seeds, dict) or not seeds:
        raise GenomeError("seed_labels: a non-empty object node -> class index")
    known = set(nodes)
    clean = {}
    for node, label in seeds.items():
        if node not in known:
            raise GenomeError("a seed label names a node not in the graph")
        clean[node] = bounded_int(label, low=0, high=k - 1, name="seed label")
    return nodes, weights, clean, k


def _neighbours(nodes, weights):
    adj = {v: [] for v in nodes}
    for (u, v), w in weights.items():
        adj[u].append((v, w))
        adj[v].append((u, w))
    return adj


def _diffuse(nodes, weights, seeds, k):
    """The mechanism: synchronous local averaging (Jacobi sweeps) with seeds clamped, from zero scores. Each node
    reads only its neighbours. Returns (scores, sweeps, converged)."""
    import numpy as np
    from scipy.sparse import csr_matrix
    index = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)
    rows, cols, vals = [], [], []
    for (u, v), w in weights.items():
        rows += [index[u], index[v]]
        cols += [index[v], index[u]]
        vals += [w, w]
    w_mat = csr_matrix((vals, (rows, cols)), shape=(n, n))
    degree = np.asarray(w_mat.sum(axis=1)).ravel()
    p = csr_matrix(w_mat.multiply(1.0 / degree[:, None]))
    clamp = np.zeros((n, k))
    is_seed = np.zeros(n, dtype=bool)
    for node, label in seeds.items():
        clamp[index[node], label] = 1.0
        is_seed[index[node]] = True
    f = clamp.copy()
    for sweep in range(1, GD_MAX_SWEEPS + 1):
        g = p @ f
        g[is_seed] = clamp[is_seed]
        moved = float(np.max(np.abs(g - f)))
        f = g
        if moved <= GD_TOL:
            return f, sweep, True
    return f, GD_MAX_SWEEPS, False


def _labels_from(scores, nodes, k):
    out = {}
    for i, v in enumerate(nodes):
        row = [float(x) for x in scores[i]]
        top = max(row)
        out[v] = -1 if top <= 0.0 else row.index(top)
    return out


def diffusion_solve(data, budget):
    nodes, weights, seeds, k = _input(data)
    scores, sweeps, converged = _diffuse(nodes, weights, seeds, k)
    if not converged:
        return answer(None, {"reason": "not converged", "sweeps": sweeps}, status="UNKNOWN",
                      missing=[f"local averaging did not settle within {GD_MAX_SWEEPS} sweeps (slow mixing)"])
    scores = [[float(x) for x in row] for row in scores]
    labels = _labels_from(scores, nodes, k)
    return answer({"labels": labels, "scores": {v: scores[i] for i, v in enumerate(nodes)}},
                  {"method": "harmonic label propagation by Jacobi sweeps, seeds clamped, zero start",
                   "sweeps": sweeps, "stop_tolerance": GD_TOL})


def _components(nodes, adj):
    seen, comps = set(), []
    for v in nodes:
        if v in seen:
            continue
        stack, comp = [v], []
        seen.add(v)
        while stack:
            u = stack.pop()
            comp.append(u)
            for x, _ in adj[u]:
                if x not in seen:
                    seen.add(x)
                    stack.append(x)
        comps.append(sorted(comp))
    return comps


def harmonic_direct(nodes, weights, seeds, k):
    """Independent of the mechanism: per connected component, solve the Dirichlet problem (D_UU - W_UU) f_U = W_UL f_L
    directly (dense NumPy); components without a seed get None."""
    import numpy as np
    adj = _neighbours(nodes, weights)
    exact = {}
    for comp in _components(nodes, adj):
        free = [v for v in comp if v not in seeds]
        if not any(v in seeds for v in comp):
            for v in comp:
                exact[v] = None
            continue
        for v in comp:
            if v in seeds:
                exact[v] = [1.0 if c == seeds[v] else 0.0 for c in range(k)]
        if not free:
            continue
        pos = {v: i for i, v in enumerate(free)}
        a = np.zeros((len(free), len(free)))
        b = np.zeros((len(free), k))
        for v in free:
            i = pos[v]
            for x, w in adj[v]:
                a[i, i] += w
                if x in pos:
                    a[i, pos[x]] -= w
                else:
                    b[i, seeds[x]] += w
        sol = np.linalg.solve(a, b)
        for v in free:
            exact[v] = [float(x) for x in sol[pos[v]]]
    return exact


def _shape(output, nodes, k):
    if not isinstance(output, dict) or set(output) != {"labels", "scores"}:
        return False
    labels, scores = output["labels"], output["scores"]
    return (isinstance(labels, dict) and isinstance(scores, dict) and sorted(labels) == nodes
            and sorted(scores) == nodes
            and all(type(x) is int and -1 <= x < k for x in labels.values())
            and all(isinstance(s, list) and len(s) == k and all(type(x) in (int, float) and math.isfinite(x)
                                                                for x in s) for s in scores.values()))


def diffusion_verify(data, output, certificate):
    nodes, weights, seeds, k = _input(data)
    if not _shape(output, nodes, k):
        return {"output_shape": False}
    exact = harmonic_direct(nodes, weights, seeds, k)
    scores_ok, labels_ok, abstain_ok = True, True, True
    for v in nodes:
        claimed, label, truth = output["scores"][v], output["labels"][v], exact[v]
        if truth is None:
            abstain_ok = abstain_ok and label == -1 and all(x == 0 for x in claimed)
            continue
        scores_ok = scores_ok and all(abs(a - b) <= GD_SCORE_TOL for a, b in zip(claimed, truth))
        top = max(truth)
        labels_ok = labels_ok and 0 <= label < k and truth[label] >= top - GD_TIE and top > 0
    return {"output_shape": True, "scores_match_the_direct_harmonic_solve": scores_ok,
            "labels_are_the_harmonic_argmax": labels_ok, "seedless_components_abstain": abstain_ok,
            "seeds_kept": all(output["labels"][v] == c for v, c in seeds.items())}


def diffusion_instance(seed):
    r = random.Random(f"genome:develop_diffusion:{seed}")
    kind = ("balanced", "imbalanced", "one_seed_per_class", "weighted")[seed % 4]
    k = r.randint(2, 5)
    n = r.randint(60, 220)
    if kind == "imbalanced":
        share = sorted((r.paretovariate(1.2) for _ in range(k)), reverse=True)
        sizes = [max(8, int(n * s / sum(share))) for s in share]
    else:
        sizes = [max(8, n // k + r.randint(-5, 5)) for _ in range(k)]
    names, label = [], []
    for c, size in enumerate(sizes):
        for i in range(size):
            names.append(f"c{len(names):03d}")
            label.append(c)
    order = list(range(len(names)))
    r.shuffle(order)                       # node names carry no class information
    names = [names[i] for i in order]
    label = [label[i] for i in order]
    mixing = r.uniform(0.05, 0.45)
    degree = r.uniform(4, 10)
    total = len(names)
    edges = {}
    for i in range(total):
        for j in range(i + 1, total):
            same = label[i] == label[j]
            p = degree * (1 - mixing) / sizes[label[i]] if same else degree * mixing / max(1, total - sizes[label[i]])
            if r.random() < p:
                w = round(r.uniform(1, 3) if same else r.uniform(0.2, 1.5), 3) if kind == "weighted" else 1
                edges[(names[i], names[j])] = w
    present = sorted({x for e in edges for x in e})
    truth = {names[i]: label[i] for i in range(total) if names[i] in set(present)}
    seeds = {}
    for c in range(k):
        members = sorted(v for v, cl in truth.items() if cl == c)
        if not members:
            continue
        count = 1 if kind == "one_seed_per_class" else max(1, int(len(members) * r.uniform(0.02, 0.06)))
        for v in r.sample(members, min(count, len(members))):
            seeds[v] = c
    data = {"graph_edges": [[u, v, w] for (u, v), w in edges.items()], "seed_labels": seeds, "num_label_classes": k}
    return data, {"labels": truth, "kind": kind, "mixing": mixing}


def diffusion_subregion(data):
    nodes, weights, seeds, k = _input(data)
    return ("few_seeds" if len(seeds) <= 2 * k else "more_seeds") + ("_sparse" if len(weights) < 3 * len(nodes)
                                                                      else "_dense")


def diffusion_score(data, truth, output):
    nodes, weights, seeds, k = _input(data)
    targets = [v for v in nodes if v not in seeds]
    if output is None:
        return {"quality": 1.0 / k, "category": "abstain"}
    labels = output.get("labels") if isinstance(output, dict) else None
    if (not isinstance(labels, dict) or sorted(labels) != nodes
            or not all(type(x) is int and -1 <= x < k for x in labels.values())
            or any(labels[v] != c for v, c in seeds.items())):
        return {"quality": -1.0, "category": "wrong"}
    accuracy = sum(labels[v] == truth["labels"][v] for v in targets) / max(1, len(targets))
    return {"quality": accuracy, "category": "correct" if accuracy > 1.0 / k else "wrong"}


def _one_hot(nodes, labels, k):
    return {"labels": labels, "scores": {v: [1.0 if c == labels[v] else 0.0 for c in range(k)] for v in nodes}}


def _nearest_seed(nodes, weights, seeds):
    """Multi-source BFS by hop count from the seeds; ties to the lowest class; unreachable nodes -1."""
    adj = _neighbours(nodes, weights)
    labels = {v: -1 for v in nodes}
    frontier = sorted(seeds, key=lambda v: (seeds[v], v))
    for v in frontier:
        labels[v] = seeds[v]
    while frontier:
        nxt = {}
        for u in frontier:
            for x, _ in adj[u]:
                if labels[x] == -1:
                    nxt[x] = min(nxt.get(x, labels[u]), labels[u])
        for x, c in nxt.items():
            labels[x] = c
        frontier = sorted(nxt)
    return labels


def diffusion_nearest_seed(data):
    """Baseline: each node takes the class of its nearest seed by hop count (ties to the lowest class)."""
    nodes, weights, seeds, k = _input(data)
    return _one_hot(nodes, _nearest_seed(nodes, weights, seeds), k)


def diffusion_community_vote(data):
    """Competitor: the central structural method. NetworkX Louvain communities (seed 0, weighted), each labelled by
    the majority class of its seeds (ties to the lowest class); a community with no seed falls back to the nearest
    seed by hop count."""
    import networkx as nx
    nodes, weights, seeds, k = _input(data)
    g = nx.Graph()
    g.add_weighted_edges_from((u, v, w) for (u, v), w in weights.items())
    near = _nearest_seed(nodes, weights, seeds)
    labels = dict(near)
    for comm in nx.community.louvain_communities(g, weight="weight", seed=0):
        votes = [0] * k
        for v in comm:
            if v in seeds:
                votes[seeds[v]] += 1
        if max(votes) > 0:
            winner = votes.index(max(votes))
            for v in comm:
                labels[v] = seeds.get(v, winner)
    return _one_hot(nodes, labels, k)


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="developmental.diffusion.harmonic_labels", version="1.0.0", family="develop_diffusion",
            layer=4, operation="propagate_graph_labels", epistemic_class="estimate",
            subgeometry="semi-supervised node labelling on an undirected weighted graph from a few verified seed "
                        "labels (evidence spreading over a claim-support or dependency graph)",
            source_provenance="Zhu, Ghahramani and Lafferty (2003) harmonic functions; Zhou et al. (2004) local and "
                              "global consistency; Doyle and Snell (1984) random walks and electric networks",
            native_representation="edge list [u, v, weight], seed labels {node: class}, number of classes",
            required_inputs=("graph_edges", "seed_labels", "num_label_classes"),
            output_contract={"labels": "{node: class or -1 (no seed reachable)}",
                             "scores": "{node: [class score]} (harmonic first-passage probabilities)"},
            algorithm_or_runtime="synchronous local averaging (Jacobi sweeps on the random-walk matrix, SciPy "
                                 "sparse), seeds clamped, zero start, until no score moves by more than 1e-11",
            parameters={"stop_tolerance": GD_TOL, "max_sweeps": GD_MAX_SWEEPS},
            memory_model="one score vector per node (the local state); nothing persists across requests",
            learning_rule="none (the fixed point is determined by the graph and the seeds)",
            composition_inputs=("graph of related claims or components", "verified labels"),
            composition_outputs=("label per node", "class scores (confidence) per node"),
            evidence_type="developmental_trace",
            verification_method="per connected component, the harmonic Dirichlet system solved directly in NumPy "
                                "(not by sweeps); claimed scores within 1e-6 of it, labels its argmax (classes within "
                                "1e-7 of the top accepted), seedless components abstain with zero scores, seeds kept",
            confidence_semantics="the scores are the harmonic solution to 1e-6; a score is the probability that a "
                                 "random walk from the node reaches a seed of that class first, not the probability "
                                 "that the label is true",
            resource_profile="O(sweeps x edges); sweeps grow with the graph's mixing time",
            latency_profile="milliseconds to seconds at benchmark size; slow on poorly connected graphs",
            known_strengths=("local: each node reads only its neighbours, so it parallelises and degrades "
                             "gracefully", "no tuning parameter", "scores carry a calibrated-looking ordering of "
                             "confidence", "abstains where no evidence reaches"),
            known_failure_modes=("few seeds in a large graph: the harmonic solution flattens and labels follow seed "
                                 "proximity and degree rather than cluster structure",
                                 "class imbalance in seeds biases the argmax toward the seeded majority",
                                 "heterophilous graphs (links mostly across classes) defeat any diffusion",
                                 "slow mixing makes the sweeps slow (UNKNOWN at the sweep cap)"),
            counterindications=("graphs whose edges join unlike nodes (dependency direction, conflict links)",
                                "directed relations where direction carries meaning",
                                "node features carrying more signal than the links (use a feature model)"),
            abstention_conditions=("UNKNOWN when the sweeps do not settle within the cap",
                                   "per node: label -1 where no seed shares the connected component"),
            benchmark_suite="planted-partition graphs with 2-5 classes, 60-220 nodes, mixing 0.05-0.45, mean degree "
                            "4-10: balanced, Pareto-imbalanced, one seed per class, and weighted (stronger links "
                            "inside a class); 2-6% of nodes seeded; quality is accuracy on non-seed nodes against "
                            "the planted classes; seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="nearest seed by hop count",
            competitor="central structural method: NetworkX Louvain communities, each labelled by its seeds' "
                       "majority (nearest seed where a community has none)",
            dependency="scipy", buildability="BUILDABLE_NOW", lineage=LINEAGE),
        solve=diffusion_solve, verify=diffusion_verify, instance=diffusion_instance, score=diffusion_score,
        baseline=diffusion_nearest_seed, competitor=diffusion_community_vote, subregion=diffusion_subregion,
        tolerance=1e-12),
]
