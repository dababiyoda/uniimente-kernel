# Metered worker spend, live, 2026-10-07

Kernel commit `ce88162` (branch `claude/greg-one-mind-converged`), after commit `53e0b3e` (metered spend).
Operator test key, not Alfonso's. Body `/tmp/greg-meter/body` (ephemeral).

One composed mission (`research-mission.json`, `greg.templates.research_post`): live pypi.org/project/ortools
browser session -> typed edge -> `facts.json` -> Claude Code worker -> DALEOBANKS verify -> publish request.
The publish decision was deliberately left unanswered: this run proves spend booking, not publishing.

| Action | Booked `cost_usd` | `cost_cap_usd` | `provider_reported_usd` | `spend_basis` |
|---|---:|---:|---:|---|
| `draft-post` (`worker.commission`) | 0.02486 | 2.0 | 0.0248602 | provider_reported |

Mission `spent_usd` after the worker: **0.02486** (the 2026-10-07 P6 run, before the patch, booked 2.00 for a
0.025 report). Draft: `The latest OR-Tools release on PyPI is ortools 9.15.6755. Recent prior versions:
9.14.6206, 9.13.4784, 9.12.4544, 9.11.4210.`

Limit: the reported figure is the Claude Code CLI's `total_cost_usd`, passed through GREG's adapter; it is the
provider's accounting, not an invoice reconciliation.
