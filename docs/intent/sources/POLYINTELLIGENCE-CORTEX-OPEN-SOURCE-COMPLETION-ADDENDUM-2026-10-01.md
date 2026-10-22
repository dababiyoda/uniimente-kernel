# POLYINTELLIGENCE CORTEX / FULL MIND — open-source completion addendum

**Date:** 2026-10-01  
**Applies to:** the existing Polyintelligence Cortex / Seed Genome coding-agent build directive and subsequent full-mind implementation work.  
**Founder intent:** `INTENT-20261001-open-source-mechanism-harvest`.

This addendum is controlling where the earlier directive is narrower.

## 1. Open-source mechanism harvesting is a build primitive

While building the currently achievable GREG Body + Organs + Mind, do not default to writing solved technology from scratch.

For every material CapabilityDeficit:

1. search existing UNIIMENTE implementations and historical branches;
2. search maintained free/open-source libraries and repositories;
3. search educational/mechanism atlases and primary technical literature;
4. identify production implementations and substitutes;
5. classify each candidate as DISCOVER, DEPEND, VENDOR-SLICE, FORK/SUBTREE, or RECOMBINE;
6. verify exact upstream revision, license/notices, maintenance/security, hardware/platform fit, transitive dependencies, assumptions and failure modes;
7. compare reuse against the simplest local implementation;
8. integrate only the smallest coherent mechanism through canonical contracts;
9. qualify it with native-domain tests, adversarial tests, resource measurements and rollback;
10. preserve provenance and a replacement interface.

Use stars/popularity only as discovery signals. They are not qualification.

## 2. TheAlgorithms and similar repositories

Treat `TheAlgorithms/Python`, `cp-algorithms/cp-algorithms`, Build-Your-Own-X and Awesome-style collections as high-value **mechanism atlases**.

TheAlgorithms/Python is explicitly educational. Its README warns that implementations may be less efficient than standard-library alternatives. Therefore:

- search it aggressively for algorithmic primitives and implementation examples;
- copy/adapt a narrow implementation only after exact license/provenance and production fitness are checked;
- prefer maintained production libraries when available;
- never claim that catalog presence equals a GREG capability.

## 3. Production source ecology for the full mind

Candidate source families include, but are not limited to:

- numerical/scientific: SciPy;
- symbolic/exact: SymPy;
- graph: NetworkX;
- operations research: OR-Tools, CVXPY, HiGHS;
- causal: PyWhy / DoWhy;
- probabilistic: pgmpy and other qualified probabilistic-programming libraries;
- game / multi-agent: OpenSpiel;
- control: python-control and appropriate MPC/state-estimation libraries;
- evolutionary / multiobjective: DEAP, pymoo;
- active inference: pymdp as an experimental source;
- neural/cognitive mechanisms: Nengo;
- cognitive-architecture precedent: Soar;
- algorithm/mechanism discovery: TheAlgorithms, cp-algorithms, AIMA.

This is a starting map, not a whitelist. Search current sources at implementation time.

## 4. Mechanism Recombination Foundry is what follows reuse, not what replaces it

Foundry should not reinvent a standard solver, graph traversal, Bayesian update, PID controller or scheduling engine merely to appear novel.

When existing components do not satisfy the target effect:

- decompose candidate repositories into causal primitives;
- preserve only useful invariants;
- mutate authority, information, incentive, resource, timing or topology where needed;
- recombine multiple mechanisms;
- require an emergent capability that no source component supplies alone;
- benchmark against the strongest straightforward composition;
- retain only the residual novel mechanism.

## 5. No repository dumping

Whole-repository copying is permitted only when a coherent subsystem boundary, compatible license, update ownership and measured integration advantage justify it.

Otherwise prefer:

`upstream dependency > narrow adapter > vendored slice > maintained fork > custom rewrite`

according to measured total cost, reliability, replaceability and legal/security burden.

Do not:
- vendor entire repositories to inflate capability count;
- erase upstream notices or provenance;
- rewrite code merely to launder an incompatible license;
- assume top-level license covers every model, dataset, asset or submodule;
- let imported frameworks create a second Kernel, scheduler, registry, mission path, learning plane or authority service.

## 6. Capability acquisition is not authority

Keep separate:

`discovered -> inspected -> license-qualified -> installable -> installed -> tested -> registered -> available -> eligible -> attached -> active -> authorized -> externally verified`

No transition is implied by the prior state.

Runtime self-installation, self-attachment and self-promotion remain prohibited unless separately authorized by the canonical authority system.

## 7. Full-machine completion supersedes VEPMC as a development stopping condition

VEPMC remains a required real-device verification milestone. It is **not** permission to stop coding the rest of the currently achievable machine.

The controlling development loop is:

`reconstruct complete Body + Organs + Mind boundary -> identify highest-priority unfinished mechanism -> search/reuse/recombine/build -> integrate -> verify -> update boundary -> repeat`.

A seed, experiment, benchmark, PR, test suite, proof, smallest falsifiable increment or VEPMC preparation is an intermediate engineering step.

Stop implementation only where further completion is genuinely blocked by:
- unavailable founder authority or a consequential decision only the founder can make;
- unavailable hardware/resource;
- unavailable external evidence or real-world participant;
- law/safety/rights constraints;
- indispensable technology not currently available at required maturity.

Otherwise continue.

## 8. P5–P10 interpretation

- **P5 demand-led repertoire expansion:** default to qualified open-source production implementations before hand-writing families.
- **P6 heterogeneous composition:** compose independently qualified mechanisms and measure marginal lift.
- **P7 Cognitive Capability Genesis:** search, acquire and qualify existing mechanisms first; generate new code/algorithms only for the residual deficit.
- **P8 evolutionary cognition:** may mutate/recombine qualified implementations under protected evaluators, not license terms or constitutional constraints.
- **P9 constraint-release discovery:** vary allowed topology/communication/resources, not law, authority, consent, safety or license obligations.
- **P10 morphogenesis:** may restore function by selecting or recombining alternative qualified implementations; novel generation is only one possible repair route.

## 9. Required provenance receipt for imported mechanisms

Every adopted external mechanism must retain:

- upstream owner/repository;
- immutable revision/version and source path/package;
- source/software/model/data license and notice obligations;
- whether code is studied, depended on, vendored, forked or recombined;
- exact modifications;
- known transitive/common-mode dependencies;
- maintenance/security snapshot;
- resource/platform requirements;
- assumptions and competence boundary;
- native qualification;
- integration tests;
- replacement candidate;
- update trigger;
- rollback.

## 10. Completion question

After every material coding session answer both:

1. **What can actual GREG do now that it could not do before?**
2. **What currently achievable Body + Organs + Mind mechanism is still missing, and which existing open-source/public mechanisms can eliminate most of that deficit before new invention is attempted?**

Then continue if unblocked.
