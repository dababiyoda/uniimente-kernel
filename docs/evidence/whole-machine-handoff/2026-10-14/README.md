# Whole-machine handoff evidence — 2026-10-14

Recorded on the `claude/greg-whole-machine-convergence` tree at `57dce89`, in a cloud development container.
These are not founder-device runs.

- `rehearsal-summary.json` is the output of `python -m greg rehearse --dir <scratch>`, with wall time, peak RSS and CPU
  measured around it. Absolute paths point to a scratch directory that no longer exists. A REHEARSAL throwaway key
  authenticates no one, and the run counts toward no VEPMC.
- `first-mission-trace.json` is `python scripts/mission_trace.py <scratch>/body m:first-mission-789fe5a98a`, read from
  that body's ledger.
- `first-mission-dossier.md` is the private dossier that mission delivered.
