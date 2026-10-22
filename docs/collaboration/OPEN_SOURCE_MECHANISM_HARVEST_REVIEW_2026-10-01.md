# Open-source mechanism harvesting — recursive founder-intent review

**Date:** 2026-10-01  
**Level:** Standard material decision  
**Founder intent:** `INTENT-20261001-open-source-mechanism-harvest`  
**Authority impact:** none. This changes development selection, provenance and contributor obligations; it does not grant runtime authority.

## Decision

**RETAIN.** Open-source/public mechanisms become the default supply chain before original implementation. Every specific imported dependency, vendored slice, fork or generated capability remains separately qualified and reversible.

## Five perspectives

### Founder-Intent Steward
The founder wants the complete currently achievable Body + Organs + Mind built faster by exploiting existing human work rather than repeatedly rebuilding solved technology. The intent is not "paste repositories indiscriminately"; it is "use the world's lawful reusable machinery as construction feedstock, then invent only what remains missing."

### Systems Architect
The strongest architecture is not a giant vendored monorepo. It is a source-to-capability pipeline:

`CapabilityDeficit -> source search -> candidate mechanism cards -> license/security/fit gate -> dependency/vendor/fork/recombine choice -> sandbox qualification -> canonical adapter -> Capability Genome -> mission path`.

This preserves replaceability and prevents imported repositories from becoming parallel control planes.

### Adversarial Reviewer
Primary risks are license contamination, hidden paid/cloud dependencies, stale/abandoned code, educational-code performance, transitive vulnerabilities, dependency explosion, duplicate authority, common-mode failures and upstream API churn. Popularity and stars are weak signals.

### Operator / Maintainer
Dependencies should be lazy, pinned and removable. Prefer normal package dependencies when upstream maintenance is valuable; vendor only narrow stable primitives when dependency overhead is worse. Every import needs an update/rollback path and a replacement interface.

### Evidence / Welfare Guardian
Open source is not automatically safe, private, fair or correct. Imported code still needs data-rights, privacy, security and consequence review. Public source provenance must remain visible so users and maintainers can challenge and replace it.

## Pass 1 — strengthen the shortcut

### Baseline
Current doctrine already says acquire before invent and prefers open-source-first software, but the active guidance mostly frames open source as a way to avoid paid providers.

### Do nothing
Benefit: no new governance.  
Failure: coding agents can still rebuild algorithms/mechanisms from scratch or treat source repositories as mere references rather than reusable engineering feedstock.

### Simplest viable alternative
Add one standing rule: search open source before coding.  
Failure: too vague; it does not distinguish dependency, narrow vendoring, whole-repo import, or educational/reference code.

### Strongest competing architecture
Mirror or vendor large collections of useful repositories into UNIIMENTE and expose them wholesale.  
Benefit: maximal immediate surface area.  
Failure: dependency sprawl, license mixture, duplicated abstractions, update burden, security surface and false capability claims.

### Reversible experiment selected
Governance-only correction plus a reusable source map. The next real CapabilityDeficit must demonstrate the pipeline on one missing cognition family before any repository-scale import is normalized.

### Strengthened design
1. Five explicit reuse modes: DISCOVER, DEPEND, VENDOR-SLICE, FORK/SUBTREE, RECOMBINE.
2. A source qualification record: upstream repo, immutable revision, path/package, license, maintenance/security evidence, primitive, assumptions, integration seam, tests, replacement and rollback.
3. Educational atlases such as TheAlgorithms and cp-algorithms default to DISCOVER.
4. Maintained domain libraries default to DEPEND behind adapters when they beat custom code.
5. Foundry runs only after the residual CapabilityDeficit is named.

### Pass-1 disadvantages
- **D1 supply-chain concentration:** a popular upstream can become a hidden critical dependency.
- **D2 legal/provenance burden:** copied code can create notice or distribution obligations.
- **D3 complexity:** a broad search can consume more time than a trivial implementation.
- **D4 qualification gap:** educational/reference algorithms can pass toy tests and still be poor production choices.
- **D5 common mode:** multiple "independent" mechanisms may share the same upstream implementation or parser.

## Pass 2 — attack the strengthened design

### Attack summary
Assume agents optimize for speed. They may paste an attractive implementation, cite an MIT-looking top-level license while missing subcomponent terms, import a full framework for one function, claim capability because tests pass, or use two wrappers around the same library as independent verification.

### New weaknesses and strengthening response
- **License ambiguity:** require exact file/package/model/data license at the pinned revision and retain notices for copied/substantial portions.
- **Dependency bloat:** require a complexity comparison between package dependency, vendored slice and local implementation.
- **Stale security:** record upstream maintenance/security status at adoption and add a review trigger.
- **False production qualification:** require native-domain tests and a simpler/stronger baseline; repository popularity is never proof.
- **False independence:** receipts disclose shared upstreams, parsers, models, datasets and solvers.
- **Whole-repo capture:** repository-scale imports need a demonstrated coherent subsystem boundary; otherwise extract only the useful mechanism.
- **Runtime self-expansion:** acquisition/build remains separate from attachment, activation and authority.

### Pass-1 disadvantage dispositions
- **D1:** accepted with replaceable adapters, pinned revisions and substitutes; review on upstream failure/change.
- **D2:** resolved procedurally by mandatory provenance/license records; prohibit reuse when compatibility is unresolved.
- **D3:** accepted with proportionality: trivial, well-understood functions may be written locally when search cost exceeds expected reuse value, but the rationale is recorded for material work.
- **D4:** resolved by classifying educational sources as discovery-first and requiring production qualification.
- **D5:** accepted with dependency disclosure and fault-diverse verification requirements.

### Residual risks
- License interpretation can still require professional counsel for consequential distribution.
- Upstream vulnerabilities and abandonment can occur after adoption.
- Fast-moving AI/model repositories can change weights, terms and behavior independently of source code.
- A source atlas can become bureaucracy if agents catalog mechanisms without integrating them.

### Rollback
Revert this governance branch. No runtime capability, package, service, authority or deployment is activated by this record.

### Kill criteria
Kill or narrow this doctrine if measured engineering time spent searching/qualifying repositories consistently exceeds the time and quality benefit of reuse for the affected class, or if reuse repeatedly creates unmanageable legal/security/maintenance coupling. Preserve the intent to avoid needless rebuilding even if the specific mechanism changes.
