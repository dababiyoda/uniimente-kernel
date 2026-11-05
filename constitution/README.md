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

**Integrity-protected.** All five files are listed in
`governance/integrity/manifest.json`; `python -m governance.integrity --check`
(Canonical CI, authority job) fails on any change without a founder-signed
authorization, and on any new `.ucl` here that nothing authorized. Changing one
is a constitutional amendment under `amendment-policy.ucl`, not an edit. Frozen
historical copies for the sealed Package 3 experiment live separately in
`evolution/repair/continuity/`. `scripts/ci/check_authority_singleton.py` fails
if a second `constitution.ucl` appears anywhere.
