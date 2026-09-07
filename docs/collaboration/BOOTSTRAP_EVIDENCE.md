# Collaboration Bootstrap Evidence — 2026-09-07

Status: inspection and draft-preparation evidence. This file does not ratify ownership, merge anything, activate a workflow on a protected branch, or authenticate the founder cryptographically.

## Inspected repositories and exact default-branch revisions

- `dababiyoda/uniimente-kernel` — `bcbb1ab4a0c42cda4a97aec42a11125753962762`
- `dababiyoda/DALEOBANKS` — `ed5e95d7f48e006d180b972efe138179325c31d2`
- `dababiyoda/WealthMachineIntelligence` — `ec84b6a2eec4efbc07bed7f167da81f5e25d890c`
- `dababiyoda/RAILSCOUT` — `c255ff323aa889ec198962a7bac47d21b6074422`
- `dababiyoda/PumpStation` — `df6a732f44412c626098ee9591b9d19f420d02dd`

## Primary-source observations

1. The kernel already contains `docs/RECURSIVE_COLLABORATION_PROTOCOL.md`, a founder-intent ledger, repository rationalization material, collaboration handoffs, and a proposed architecture ownership map. This bootstrap therefore routes workers into the existing system instead of creating a second governance canon.
2. The inspected kernel default branch has `CLAUDE.md` but no root `AGENTS.md`.
3. The inspected DALEOBANKS, WealthMachineIntelligence, RAILSCOUT, and PumpStation default-branch root trees did not show a root `AGENTS.md`.
4. The existing ownership map says, as a PROPOSED record, that kernel owns constitution/authority/shared contracts and that DALEOBANKS and WealthMachineIntelligence are specialist consumers. Because the map itself says it is proposed, this bootstrap treats it as routing evidence, not as automatically ratified law.
5. WealthMachineIntelligence already has `Instructions.md`; the bootstrap must preserve it and point workers to both repository-specific instructions and the shared guide rather than overwrite local operating rules.
6. RAILSCOUT default branch was README-only at inspection, so any richer claims about its runtime are not established from that default branch.
7. Kernel open draft chain inspected on 2026-09-07 includes #86 and the experimental #87 -> #88 -> #90 -> #92 -> #94 line. #94 states it is draft/simulation-only, not whole-institution closure, and reports three broader-suite failures. This bootstrap does not merge, supersede, or activate that chain.

## Intentionally excluded from automatic installation

- `dababiyoda/build-your-own-x`: treated as a mechanism/reference corpus unless a separate founder decision makes it an operating organ. Project-specific governance files are not injected into the reference source in this bootstrap.
- `dababiyoda/RESEARCH-IN`: not designated by the inspected ownership records as a current canonical operating organ. It remains outside this five-repository rollout pending a scoped ownership/use decision.

This exclusion is conservative. It avoids converting every accessible repository into an institutional runtime dependency merely because it is available through the GitHub app.

## Tool and settings limits

- The available GitHub connector exposes issues, PRs, branches, files and Actions, but no GitHub Discussions create/update action was available during this session. The founder explicitly allowed a Discussion **or a file**, so the implementation uses a versioned canonical file plus an issue-based coordination surface. A human can later enable/pin a Discussion that points to the canonical file.
- Repository rulesets/required-check settings are not changed by these draft files. Requiring a new status before it has run could lock normal contribution, so adoption is intentionally staged.
- A root instruction file cannot force every coding client to read it. Clients that do not discover `AGENTS.md` require a saved startup instruction or equivalent configuration. That is a tool-administration step, not something a repository file can truthfully claim to have completed.

## Evidence tiers

- Repository tree/file/PR data above: primary-source GitHub connector reads.
- Claims in PR descriptions about test counts: inspected project claims, not independently rerun in this session.
- New workflow unit tests: source prepared in this draft. Passing status is not claimed until CI or an execution environment runs them.
- Expected process benefit: hypothesis. Baseline metrics are `NOT_MEASURED`; the guide requires a five-completed-PR pilot before retention is claimed.

## Strongest counterexample

A disciplined team can collaborate effectively with only a short `AGENTS.md`, good issue ownership, required reviews and clean PRs. If the receipt system adds ceremony without reducing stale-context rework, duplicate work or founder reconstruction, the simpler pointer-only design should win. The pilot explicitly preserves that rollback.
