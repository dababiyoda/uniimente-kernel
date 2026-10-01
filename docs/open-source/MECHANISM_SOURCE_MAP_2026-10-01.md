# Open-source mechanism source map — 2026-10-01

Purpose: accelerate full-machine construction by turning public/open-source work into **qualified mechanism supply**, not by dumping repositories into the active runtime.

The repositories below were checked as public and non-archived through GitHub metadata on 2026-10-01. Exact license, subcomponent license, model/data license, maintenance/security state and revision **must be re-verified at adoption time**.

## Reuse modes

| Mode | Meaning | Default |
| --- | --- | --- |
| DISCOVER | Learn mechanisms, algorithms, constraints and alternatives; no runtime dependency implied | Educational/index repositories |
| DEPEND | Use maintained upstream package/service behind a narrow replaceable adapter | Mature production libraries |
| VENDOR-SLICE | Copy/adapt the minimum lawful source slice with notices, pinned provenance and tests | Small stable primitives when full dependency is worse |
| FORK/SUBTREE | Preserve a coherent upstream subsystem with explicit update ownership | Only when subsystem-level reuse is justified |
| RECOMBINE | Extract/mutate mechanisms from multiple sources with Foundry to close a residual CapabilityDeficit | Novel UNIIMENTE-specific behavior |

## Candidate mechanism atlas

| Family | Candidate source | Default use | What it can teach/supply |
| --- | --- | --- | --- |
| Broad algorithm vocabulary | `TheAlgorithms/Python` | DISCOVER; occasional VENDOR-SLICE after license/quality check | search, graphs, dynamic programming, numerical methods, ML, compression, crypto, geometry and many other primitives |
| Algorithm explanations / competitive programming | `cp-algorithms/cp-algorithms` | DISCOVER | complexity, graph algorithms, geometry, number theory, data structures, optimization techniques |
| Classical AI | `aimacode/aima-python` | DISCOVER | search, CSP, planning, games, probability, learning |
| Numerical/scientific | `scipy/scipy` | DEPEND | optimization, integration, statistics, signal processing, linear algebra |
| Exact/symbolic | `sympy/sympy` | DEPEND | algebra, exact arithmetic, symbolic equations/calculus/rewriting |
| Graph intelligence | `networkx/networkx` | DEPEND | paths, flow, connectivity, centrality, DAG/SCC and structural graph analysis |
| Discrete OR | `google/or-tools` | DEPEND | CP-SAT, scheduling, routing, flow, assignment |
| Convex optimization | `cvxpy/cvxpy` | DEPEND | declarative convex optimization |
| LP/MIP solver | `ERGO-Code/HiGHS` | DEPEND | high-performance linear/mixed-integer optimization backend |
| Causal inference | `py-why/dowhy` | DEPEND/RECOMBINE | identification, estimation, refutation, assumptions and causal diagnostics |
| Probabilistic graphical models | `pgmpy/pgmpy` | DEPEND | Bayesian networks, DAG models, probabilistic inference |
| Game / multi-agent decision | `google-deepmind/open_spiel` | DISCOVER/DEPEND | imperfect-information games, search, RL, multi-agent evaluation |
| Control | `python-control/python-control` | DEPEND | feedback, state-space control, stability/control design |
| Evolutionary/program search | `DEAP/deap`, `anyoptimization/pymoo` | DISCOVER/DEPEND | genetic programming, evolutionary search, multiobjective optimization |
| Active inference | `infer-actively/pymdp` | EXPERIMENTAL DISCOVER/DEPEND | explicit generative-model active-inference mechanisms |
| Neural cognitive mechanisms | `nengo/nengo` | DISCOVER/EXPERIMENT | stateful neural computation and learning rules |
| Cognitive architecture | `SoarGroup/Soar` | DISCOVER | working memory, productions, task cognition, architecture precedents |

## Discovery indexes

Use `sindresorhus/awesome`, `awesome-selfhosted/awesome-selfhosted`, existing UNIIMENTE Build-Your-Own-X material, standards indexes and primary research as maps to locate candidates. They are not evidence that every linked project is suitable.

## Qualification record required before adoption

For every material external mechanism, record:

- upstream repository and canonical owner;
- immutable commit/tag/package version and exact path/module;
- exact source/software/model/data license and notice obligations;
- maintenance activity and known security/advisory status;
- language/platform/hardware/resource fit;
- primitive/mechanism extracted;
- whether code is studied, depended on, vendored, forked or recombined;
- assumptions and unsupported conditions;
- input/output/proof contract;
- failure/recovery behavior;
- upstream/common-mode dependencies;
- project adapter and canonical owner;
- native qualification benchmark and strongest simpler alternative;
- replacement candidate and rollback;
- review trigger.

## Cortex / Foundry pipeline

`ProblemGeometry -> CapabilityDeficit -> source search -> Mechanism Cards -> qualification gate -> DEPEND/VENDOR/FORK/RECOMBINE -> sandbox benchmark -> CognitiveCapabilityProfile -> Capability Genome -> canonical GREG mission -> outcome settlement`

P5 repertoire expansion should preferentially draw from this source ecology. P7 Capability Genesis should first search and qualify existing mechanisms before generating new algorithms. P8-P10 may use Foundry/evolution/constraint-release only after existing mechanisms and straightforward compositions fail the declared requirement.

## TheAlgorithms-specific boundary

TheAlgorithms/Python currently states that its implementations are for education and may be less efficient than Python standard-library implementations. Its repository license file is MIT. Use it aggressively as a mechanism vocabulary and source of bounded, attributable transplants where justified, but prefer stronger maintained production implementations when available.

## Non-goals

- No automatic cloning of every repository.
- No runtime internet self-installation.
- No claim that catalogued capability is executable capability.
- No whole-repo import solely because the project is popular.
- No duplicate Kernel, scheduler, mission path, registry, learning plane or authority service.
- No license laundering through generated rewrites.
