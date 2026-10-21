# immune-8: not frozen, not run (decision of 2026-10-21)

**The pilot's declared rule gives NOT_VIABLE.** The best mean simulated P(RETAIN) is **0.000**, against a threshold of 0.30. All six simulated cycles in the narrowed space failed the merged adversarial gate on false-alarm violations. Details are in `pilot/README.md`.

**What this decision covers:**

- No pre-registration is drafted. Nothing is frozen and no P8 seed is drawn.
- The confirmatory seeds proposed in `DESIGN.md` section 10 stay unused. Immune-7's 8600-8839 also stay unused.

**What it rests on:**

- The space, seeds, procedures, comparators, limits, viability rule and error accounting were declared at `e7cbe72`, before any instance of seeds 4000-4999 existed.
- The gate is the merged `stress_summary` + `stress_worsened` from `09555108`.
- The lineage and the re-gating of immune-7 are in `LINEAGE.md` and `gate-audit.json`. The exposure audit is in `EXPOSURE-AUDIT.md`.

**What happens next, as declared:**

- No third immune pilot is proposed by this lane.
- The second-target recommendation is `develop_repair` (`SECOND-TARGET-SURVEY.md`). It has finite wrong-answer losses and is a measured L4 deficit.

**What only the founder can decide** (unchanged, and not made here):

- the shared `RULE`'s treatment of wrong answers (immune-7 option 4);
- adoption of cycle 6;
- data rights for M4, fpp3, NYC and SNDlib.
