# Lineage — IVIO-NEMT Venture Cell

## `first_cell.py`

| | |
|---|---|
| Original path | `morphogenesis/ivio_first_cell.py` |
| Introduced by | PR #30 (`agent/morphogenetic-control-contract`), merged into `integration/uniimente-egregore-v1` |
| Merge commit | `378d66dfb6bcab7e704a29a5c706bbbf9b91e9ea` |
| Relocated in | Package 2, from `release/canonical-v1` @ `9085860` |
| Implementation | preserved byte-for-byte; only the module docstring gained a lineage note |

**Reason for relocation.** The file declares an IVIO-NEMT-specific morphogenetic
setpoint and sat inside the core `morphogenesis/` package. Under the founder's
core-versus-venture ruling, a venture setpoint may not live in a core package.

**What did NOT move.** `morphogenesis/contracts.py` and `morphogenesis/engine.py`
are core and remain untouched. The engine evaluates targets and never activates
descendants; that behaviour is unchanged.

**Historical records are not rewritten.** `integration/egregore-v1.yaml`
`source_prs:` truthfully records that PR #30 delivered
`setpoint_control_and_ivio_first_cell`. That entry is institutional memory and
is protected — see `docs/release/package-2/PROTECTED_RECORD_HASH.txt`.

## `fixtures.py`

Preserves the healthcare-domain closure fixture formerly hardcoded as the
default in `closure/advantage_registry.py`. The core now has a generic fixture
builder requiring explicit values; this file supplies the original IVIO example
so the worked case survives intact rather than being deleted.
