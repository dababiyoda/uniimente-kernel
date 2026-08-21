# Revocation Model

Offline verification is the aperture's strength and its hardest problem. An effector that never calls home cannot learn that authority was withdrawn.

## Candidates

**A — short-lived certificates.** Bounds exposure everywhere, needs no infrastructure. But a 120s TTL is still 120s, and shortening it indefinitely reintroduces the availability problem by another route.

**B — signed revocation snapshots.** The effector holds a signed, versioned, monotonic statement of what is revoked, checkable entirely offline. But the snapshot itself goes stale, and staleness is unbounded without a rule.

**C — online validation.** Zero window, and it reintroduces exactly the availability hazard that motivated the architecture.

## Selected: hybrid

A everywhere, B distributed to every effector, and C's *freshness requirement* expressed as a **maximum staleness per consequence class** — without the network call. The organ never has to reach the Kernel. It has to hold a snapshot no older than its class permits.

| class | max TTL | max staleness | on stale/unavailable |
|---|---:|---:|---|
| `internal_read` | 3600s | 86400s | permit |
| `internal_write` | 1800s | 3600s | permit |
| `external_contact` | 900s | 900s | **refuse** |
| `financial` | 300s | 60s | **refuse** |
| `irreversible` | 120s | 0s | **human escalation** |

The asymmetry is the design. Staleness is permissive at the bottom and fail-closed at the top. An effector that cannot prove its revocation state is fresh enough **must not** perform a financial or irreversible action. Clock skew tolerance is 30s.

## Behaviours

- **Partition** — low classes continue, high classes refuse. Verification never needs the Kernel; freshness does.
- **Stale state** — per the table. Never silently permitted at the top.
- **Rollback** — a snapshot with an epoch lower than one already seen is refused (`snapshot_rollback`). Otherwise replaying an old snapshot would un-revoke authority.
- **Issuer key compromise** — every certificate signed by that key is refused.
- **Revoked actor / organ / workload** — each refused by name. A replaced workload does not inherit authority.
- **Emergency shutdown** — local containment; the organ's veto is not reachable by the Kernel.

## Residual risk

**The window is real and unsolved.** Between issuance and expiry, an effector holding a fresh-enough snapshot that predates a revocation will honour the certificate. Short TTLs bound it; they do not eliminate it. For `irreversible` the window is zero by construction, which is why that class escalates rather than refusing silently.

Threshold authorization (candidate C7) is the mitigation for the high classes and remains deferred.
