# Independent verification: Part 2 containment floor (DEC-OM-003)

**Verifier:** CLAUDE. **Date:** 2026-08-22. **Status:** evidence record — grants no
authority, promotes nothing, and changes no decision state.

Verifies the corrected Part 2 head that the founder's disposition matrix made F4/F5
conditional on. That head now exists.

## What was inspected

`agent/opus-part2-governed-boundary @ 622d76f6285061212fe1aa14fe3a94d382f687de`, read in an isolated git worktree.
Four commits since `58ec6682`, touching exactly the four files the founder's
smallest-patch plan named and nothing else:

| file | blob at this head |
|---|---|
| `containment/policy.py` | `009c4862132a8e950bc8dd087f89216a5bd3163c` |
| `containment/__init__.py` | `ced46b8563a26202b1ed4fa359f0e111a76ed2eb` |
| `containment/EVIDENCE.json` | `b512bbdb2b953e818246630a3561ea7644bd14e5` |
| `tests/unit/test_containment.py` | `fee9bda9dd7c37bed834bfaad32bbc9645a8eedd` |

## The founder's decision, and whether it holds

DEC-OM-003 decided: `irreversible` requires `ContainmentTier.MICROVM`, no fallback,
with noncompensable financial actions classified irreversible.

Their 24 containment tests pass. That is their evidence, not mine, so the floor was
attacked directly rather than read: every valid trust class crossed with every tier.

```
ATTACK: irreversible below microVM, across every valid trust class
  internal_trusted     MICROVM -> accepted (correct)
  internal_untrusted   MICROVM -> accepted (correct)
  foreign              MICROVM -> accepted (correct)
  generated            MICROVM -> accepted (correct)

  sub-microVM acceptances for irreversible: NONE - floor holds
```

Both directions matter. No trust class buys a lower tier — an insider claim of
`internal_trusted` does not soften the floor. And MICROVM stays reachable for all
four classes, so the floor is not accidentally unreachable, which would be a
different defect wearing the same green.

## Two false verifications, recorded because they nearly shipped

The first probe failed with `TypeError` on a malformed constructor call and every
tier came back "refused". The second failed on `unknown trust class` and every tier
came back "refused" again. Both looked exactly like a floor holding. Neither reached
the tier check at all.

A refusal is only evidence when the probe got far enough to be refused for the
reason under test. Only the third probe, using the real `TRUST_CLASSES` vocabulary,
actually exercised the floor.

## What this does NOT establish

Policy, not enforcement. `EnforcementKind.HYPERVISOR_BOUNDARY` is a declared
requirement; nothing here launches a microVM or proves one would contain anything.
The institution holds zero network capability and no runtime isolation, so this is a
correctly-specified gate in front of a capability that does not yet exist.

F4/F5 binding is still not done, and cannot be from here. Binding implementation
evidence needs the files present in the binding tree; these live on an unmerged
branch. The blob pins above are what makes the claim checkable in the meantime.
