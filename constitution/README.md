# constitution/

Supreme institutional law, written in UCL (`docs/UCL.md`).

| File | Defines |
|---|---|
| `constitution.ucl` | purpose, prohibitions, non-delegable matters, failure posture |
| `sovereignty.ucl` | the rank-1-to-10 sovereignty hierarchy and Alfonso's reserved authority |
| `participant-rights.ucl` | rights every participant holds and how each is enforced |
| `amendment-policy.ucl` | who may ratify amendments; what the institution may never amend itself |
| `shutdown-policy.ucl` | the unconditional shutdown path |

**Consumed by:** `compiler/` (`compile_constitution`), which every policy decision runs through.

**Sealed.** Every `.ucl` file here is byte-pinned by frozen experiment records
(`evolution/repair/spec.py`, `evolution/migration/spec.py`,
`evolution/repair/subjects.py`). Changing one is a constitutional amendment
under `amendment-policy.ucl`, not a refactor, and it will (correctly) fail the
frozen-continuity tests until a new reviewed binding is recorded.

`scripts/ci/check_authority_singleton.py` fails CI if a second `constitution.ucl`
appears anywhere in the repository.
