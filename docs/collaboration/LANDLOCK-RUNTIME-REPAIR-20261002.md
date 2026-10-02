# Landlock runtime dependency repair — 2026-10-02

Parent: `FM-LANDLOCK-20261001`; founder objective: `INTENT-20261001-FULL-MACHINE-COMPLETION`.

Hosted run [36940745930](https://github.com/dababiyoda/uniimente-kernel/actions/runs/36940745930), at `93891032d928ce3cbf804fc7589e75b0a2939231`, passed three actual Landlock probes and two MCP refusal checks, but failed retained-media MCP execution: its extension lazily loads `librt.so.1` after confinement. The full suite was not reached. This failure remains counterevidence.

This is a lightweight repair to the existing reviewed runtime dependency closure. Grant read access to the resolved `librt.so.1` file in the two architecture-specific system library locations only if it is a regular, root-owned, world-readable, non-group/world-writable ELF file. Grant no containing directory, library wildcard, write permission, provider or source admission. Preloading the entire SDK would hide missing closure; granting all installed libraries would widen the scope unnecessarily.

The native escape test now loads that lazy library after restriction and still checks private reads, writes, truncation and symlink escapes. Local focused tests: 21 passed, 3 skipped (unsupported local Landlock); hosted kernel evidence is required for the repaired head. Retain fail-closed installation on supported hosts. Rollback: revert the dependency grant and preserve refusal; do not disable OS protection to obtain green tests.

The seven linked decision records omitted the schema-required rejected-alternatives array. Restore it from each already recorded competing architecture's disadvantages and revival evidence, preserving the original two passes and the wider capability horizon. This is schema repair, not invented independent review or retrospective successful proof.

A successful repair resumes the complete Body + Organs + Mind objective automatically. Next executable dependency: pinned OCI capability packaging and execution using the observed disposable CI Docker host; context files alone will not establish completion.
