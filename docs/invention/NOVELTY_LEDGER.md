# Novelty Ledger

What is actually new here, stated narrowly enough to be checkable.

## Not new

Ed25519, canonical JSON hashing, capability objects, effect binding, signed revocation
lists, fail-closed refusal, the permissive action link from nuclear command and control.
Every primitive is prior art and is used as prior art.

## The new part: interaction geometry

Authority is a **portable twenty-field signed artifact that the effector validates
independently**, paired with an **organ-local veto the issuer cannot reach**.

Neither half is novel. The combination produces a property I have not found elsewhere in
this repository's lineage or its references: **partition makes the system more
conservative rather than less**. An effector that cannot reach the Kernel can still
verify what it holds, and an effector that cannot verify refuses. There is no state in
which losing the Kernel produces a permit.

## The emergent capability

- an organ acts correctly while unable to contact the Kernel
- an external auditor verifies attribution with no access to the institution
- a replacement workload provably cannot inherit authority
- a contract or device can be a first-class effector, because verification needs only a
  public key and a clock

## Unresolved

Whether staleness-by-consequence-class is the *right* asymmetry or merely the first one
that worked. It has not met a real partition or a real revocation emergency. Threshold
authorization for the high classes is designed and deferred.

**Patentability is not claimed and has not been assessed.**
