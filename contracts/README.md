# contracts/

Versioned JSON Schemas (draft 2020-12) shared by every organ. The filesystem is
the registry: `linker/linker.py` discovers every `*.schema.json` here, so there
is no second list to keep in sync.

- Core institutional records: `event`, `evidence`, `decision`, `outcome`,
  `capability-grant`, `workflow-execution`, `organ-manifest`.
- Venture and opportunity records: `opportunity-packet`, `venture-assessment`,
  `venture-cell-charter`, `context-packet`.
- `egregore-cognition`: ADE-1 standing-cognition output.
- `wire-*`: the DALEOBANKS↔WealthMachine wire protocol v1.1, a registered
  peripheral contract. Preserved and adapted (`adapters/`), never deleted.

This directory ships in the `uniimente-kernel-boundaries` distribution
(`pyproject.toml`) that WealthMachineIntelligence and DALEOBANKS pin. Treat
schema edits as a versioned contract change.

Check: `make contracts` (every document-local `$ref` resolves).
