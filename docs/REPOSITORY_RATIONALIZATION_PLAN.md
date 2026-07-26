# Repository Rationalization Plan

## Executive diagnosis

UNIIMENTE has strong doctrine, increasingly capable runtime modules, and explicit organ boundaries. Its primary maintainability risk is no longer missing capability. It is the multiplication of truth surfaces:

- canonical kernel contracts plus historical mirrored protocol modules;
- upstream repositories plus copied or quarantined repository snapshots;
- generated clients and compiled output stored beside authored source;
- proof artifacts, handoff documents, issues, and README claims describing overlapping states;
- multiple implementation eras remaining discoverable without a clear canonicality marker.

The remedy is not a monorepo rewrite. It is a strict source-of-truth hierarchy and staged extraction.

## Canonical ownership

| Concern | Canonical owner | Organs may contain |
|---|---|---|
| Constitution, authority, shared contracts, event spine, evidence, consequence policy | `uniimente-kernel` | pinned SDK dependency, adapters, compatibility shims |
| Public identity, media perception, publication operations | `DALEOBANKS` | organ-specific workflows and local state |
| Venture evaluation, underwriting, portfolio recommendations | `WealthMachineIntelligence` | organ-specific models and local state |
| Founder cockpit / institutional digital twin | integration application | projections and commands through contracts; no duplicate governance engine |
| Archived source and external evidence | content-addressed archive outside authored source tree | manifest, hash, provenance pointer only |

## Immediate rules

1. No repository snapshot, ZIP, build directory, dependency tree, or generated client belongs in authored source unless a documented exception exists.
2. Every copied implementation must declare `canonical_source`, `sync_method`, `version`, and `removal_trigger`.
3. Compatibility shims may re-export canonical modules but may not fork behavior.
4. README status claims must point to executable proof or be labeled proposed, simulated, or historical.
5. Proof artifacts are append-only evidence; generated build output is disposable and reproducible.
6. The cockpit consumes governance; it does not become a second constitution, event spine, ledger, autonomy ladder, or consequence gate.

## Migration waves

### Wave 0 - inventory and freeze

- Generate a machine-readable repository manifest.
- Classify every top-level path as authored source, generated, vendored, evidence, archive, runtime state, or documentation.
- Freeze new copied-source additions.
- Record exact and semantic duplicates.

### Wave 1 - hygiene

- Remove nested ZIPs and compiled output from source branches after hashes and provenance pointers are preserved.
- Expand `.gitignore` consistently across repositories.
- Add canonicality headers to compatibility shims and historical documents.
- Introduce repository maps and owner files.

### Wave 2 - contract convergence

- Complete the existing kernel contract extraction work.
- Replace organ-local copies with version-pinned SDK imports.
- Add parity tests at each organ boundary.
- Publish a compatibility and deprecation matrix.

### Wave 3 - collaboration substrate

- Add Founder Intent Ledger records.
- Require the Recursive Collaboration Protocol for material PRs.
- Add ADR and RFC indexes.
- Add automated checks for duplicate schemas, copied modules, broken provenance links, and unclassified top-level paths.

### Wave 4 - cockpit integration

- Define the cockpit as a replaceable projection and command client.
- Move embedded organ source trees to pinned dependencies or service boundaries.
- Preserve simulation fixtures separately from institutional evidence.
- Display canonical source, reality status, policy version, and evidence provenance for every major object.

## Kill criteria

Stop or regress a consolidation when it:

- weakens fail-closed behavior;
- erases provenance or contributor lineage;
- requires coordinated releases without a compatibility window;
- makes an organ unable to operate safely during kernel unavailability;
- converts historical evidence into mutable application state;
- increases the number of authorities or execution paths;
- creates a monolith without measurable maintenance or reliability advantage.

## Success metrics

- duplicate canonical implementations: 0;
- unclassified top-level paths: 0;
- material PRs with complete deliberation records: 100%;
- shared contract parity failures caught before merge: 100%;
- generated or archived bytes in authored source: trending to 0;
- time for a new contributor to identify canonical owners and run tests: under 30 minutes;
- founder intentions silently dropped: 0.