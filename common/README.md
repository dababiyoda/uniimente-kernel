# common/

Shared mechanics with no policy or authority: canonical JSON, `sha256:`
content references, and a UTC clock. It exists so one definition replaces
copies that had drifted across `foundry/`, `omnimorph/`, `loom/`,
`capabilities/`, `business/`, `identity/` and `evolution/`.

```python
from common import canonical_json, sha256_ref, is_sha256_ref, utc_now, utc_now_iso
```

`tests/unit/test_common.py` pins the byte form, so existing digests are
unchanged.

**Deliberately not migrated** (each keeps its own copy, for a reason):

- `provenance/`, `events/`, `adapters/`, `contracts/`: the published
  `uniimente-kernel-boundaries` package that consumers pin. It must not gain a
  dependency outside its four packages.
- `policy/consequence_gate.py`, `evolution/repair/`, `evolution/migration/`:
  sealed or frozen experiment artifacts.
- `egregore/contracts.py`: a *stricter* canonical form (`ensure_ascii=False`,
  `allow_nan=False`). Its digests differ from this module's for non-ASCII text,
  so unifying them would re-hash history. Two canonical forms exist on purpose;
  new code should pick one deliberately.
