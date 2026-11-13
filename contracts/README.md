# contracts/

Versioned JSON Schemas (draft 2020-12) shared by every organ. The filesystem is
the registry: `linker/` discovers every `*.schema.json` here.

- Core institutional records: event, evidence, decision, outcome,
  capability-grant, workflow-execution, organ-manifest.
- Venture and opportunity records; `egregore-cognition` (ADE-1 output).
- `wire-*`: the DALEOBANKS↔WealthMachine wire protocol v1.1, a registered
  peripheral contract, preserved and adapted (`adapters/`), never deleted.

Ships in the `uniimente-kernel-boundaries` distribution (`pyproject.toml`) that
the organs pin, so a schema edit is a versioned contract change. CI: the
contracts job runs `scripts/ci/check_schema_refs.py` (every `$ref` resolves).
