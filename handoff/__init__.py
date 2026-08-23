"""The frozen Claude/ChatGPT handoff bundle.

The contract is canonical; this docstring is not. `handoff/contract.json` carries
the ownership matrix, protocol versions, invariants, blockers and merge order.

The seal is a **bundle** seal, not a title-page seal. Hashing `contract.json`
alone would leave the schemas and vectors free to drift while the advertised
digest stayed the same, which is exactly the failure a seal is supposed to make
impossible. Instead:

    BUNDLE_MANIFEST.json   sorted path + SHA-256 for every file in the bundle,
                           including the pre-existing canonical schemas the
                           bundle depends on.
    bundle digest          SHA-256 over the exact bytes of BUNDLE_MANIFEST.json.
    SEAL.json              commit A's SHA plus that digest.

A file cannot contain the SHA of the commit that contains it, so the freeze is
two commits: commit A lands the bundle and its manifest; commit B lands the seal
naming commit A.

Verify with `python -m handoff.conform`. Nothing is imported here, so running
that module does not re-execute this package's body.
"""

__all__: list[str] = []
