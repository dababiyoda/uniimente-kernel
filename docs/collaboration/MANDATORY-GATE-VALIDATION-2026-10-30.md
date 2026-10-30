# Gate validation and deployment receipt

## Follow-up repair after real-worker testing

The original 77-test unittest result below did not cover pytest's package
collection. Canonical CI run 41016367214 failed jobs 1 and 9. Two Claude workers
independently identified the bare sibling import in the launcher test. The
repair imports through `tests.unit`, matching the real repository package.
The partial local source preparation restores the existing empty
`tests/unit/__init__.py` for verification; that file is not a new remote change.

The launcher now uses `-p` whenever `--prompt` is supplied, including an empty
prompt. No prompt retains interactive mode. An independent Codex reviewer also
found installer `..` traversal could pass lexical workspace containment; the
installer now rejects it before mutation and resolves paths after symlink checks.
Regression tests retain literal prompt arguments and prove outside settings are
not created. Current local result: **25 gate/installer/launcher + 5 workspace +
49 receipt = 79 distinct tests pass**. Pytest is unavailable in this local runtime;
hosted collection and a real launcher call remain separate checks.

Worker-reported integration evidence (not directly executed by this coordinator):
[#196 integrator's real Claude Code 2.1.314 test](https://github.com/dababiyoda/uniimente-kernel/pull/206#issuecomment-6516958131)
used headless child clients in an isolated workspace. Missing enrollment refused
Write; a scoped Write succeeded; an outside Write and overlapping claim were
refused; only the named receiver could accept the pending handoff. The worker
called Claude directly with `-p`, exposing the launcher bug fixed here.
Two other workers ran isolated direct-hook tests, not real harness invocations:
[#215](https://github.com/dababiyoda/uniimente-kernel/pull/206#issuecomment-6516930726),
[#221](https://github.com/dababiyoda/uniimente-kernel/pull/221#issuecomment-6516926048).
All three still report their live sessions UNENROLLED. The integrator reports
no harness restriction and offers adoption after a green revision; another
worker requires its session owner's instruction. Their distinct reports are
retained rather than inferred into uniform authority or installation status.

The following original receipt remains historical evidence for `44fcb227`.

Implementation scope: two new scripts, three test files, one decision/runbook,
this evidence record and the existing START_HERE pointer. Existing #206 installer
and #193 checker are reused. No product runtime source is changed.

- `python3 -m unittest discover -s tests/unit -p 'test_*gate*.py' -v`:
  23 passed. Real subprocess races admit exactly one conflicting worker; disjoint
  paths proceed; linked worktrees collide under one common git identity. Tests
  also cover restart, expiry without stealing, source/head drift, malformed events,
  scoped Write/NotebookEdit, repository-wide Bash, corruption, handoff and recovery.
- Original workspace-entry tests: 5 passed. Original inline receipt tests:
  49 passed. Total distinct tests exercised: 77.
- Separate reviewer `/root/gate_independent_review` ran the 20-test snapshot and
  extra actual launcher probes. It found two P2 defects: DB `..` containment and
  client cleanup destroying a pending handoff. Both were repaired, regression
  tests retained, and independently re-probed. No remaining P1/P2 within scope.
  Three additional launcher regressions were then rerun by the coordinator.
- Actual local installation: workspace pointers installed and checked under
  `/workspace/scratch/bd3ab4176d4b`, pointing to the reviewed partial source at
  `gate-upgrade`. The Claude PreToolUse rule is installed in the workspace's
  `.claude/settings.local.json`; a subsequent check succeeded. Existing client
  permissions/hooks are preserved by the tested merge, and a backup is kept when
  a settings file already exists.
- Installed-hook invocation tests execute the actual configured command with
  event-shaped stdin. A fake Claude executable verifies admission-before-launch,
  exact UUID/settings arguments, cleanup and handoff preservation. This fixture
  is NOT a real Claude process or global managed-policy deployment.

Inspection sources: #206 a36e75d614b71fa816135fe45c081b69553cd290; current #196
4ec006058ebe3ab376e1445181e5afc5b3704836 at intake; the protocol's five-role/two-pass
reference; official Claude hooks and CLI documentation inspected 2026-10-30:
https://code.claude.com/docs/en/hooks and
https://code.claude.com/docs/en/cli-reference . SessionStart cannot block tool
execution. PreToolUse exit 2 blocks; onFailure:block covers missing/crashing hooks.

Remaining evidence: real installed Claude version compatibility, each actual
repository checkout and other client adapter, and cross-machine coordination.
The current workspace was pruned before this turn and contains a partial source
preparation, not all 13 user checkouts. GitHub drafts alone cannot enroll them.
No credentials, private chats, global hooks or remote machines were accessed.
An operator can disable local settings, modify the shared DB, or use an uncovered
tool; this is a trusted local coordination boundary, not a hostile-host sandbox.
Arbitrary Bash can write anywhere its OS identity permits despite its exclusive
repository claim. Test success does not prove comprehension or authorized effects.

Wider rollout: existing integrator reviews exact source and enrolls real clients,
then records actual hook refusal/admission and receiver evidence on board #96.
Protected merges remain subject to existing authorization. Preserve the source
commit, negative findings, this validation record and all previous SOP lineage.
