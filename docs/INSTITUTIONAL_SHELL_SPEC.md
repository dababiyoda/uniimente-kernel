# Institutional Shell and Pipelines — specification

Specifies technology **#14, "Institutional shell and pipelines"** (`foundry/arsenal.py`:
category `operations`, control surfaces `governance` and `workflow`, consequence class
`internal_write`, dependencies #1 and #8).

## Why this document exists

Until now #14 was the only technology on the 55-item ladder awarded **no rung at all**.
Not BLUEPRINT — nothing. The ladder's floor requires a document to point at, the
arsenal named this technology without specifying it, and `python -m blueprint`
reported it as `UNSUPPORTED` rather than quietly rounding it up to BLUEPRINT.

That refusal was correct and this document answers it. Writing a specification so a
row stops looking bad would be the exact failure the blueprint's own adversarial pass
names: *"a future session can lift a rung by adding a thin test rather than a real
capability."* So this specification is accompanied by an implementation, tests and a
closure registration in the same change. A rung earned by ceremony is worse than an
honest zero.

## The operator problem this solves

The kernel now has four separate read-only reporters, each with its own entry point
and its own output shape:

| Command | Answers |
|---|---|
| `python -m blueprint` | how mature is each of the 55 technologies, and what can be built next |
| `python -m linker` | which organs are connected, and what did not resolve |
| `python -m handoff.conform` | is the frozen ChatGPT bundle intact |
| `python -m developmental` | developmental substrate state |

Nothing composes them. An operator asking "what is the state of the institution?"
must run four commands, hold four output formats in their head, and reconcile the
overlaps by eye. There is no single surface, and no way to name a recurring sequence
of checks so it can be re-run identically.

## What the shell is

A **read-only operator surface** that composes existing reporters into named
pipelines and prints one institutional summary.

It is a *composition layer*. It owns no institutional state, computes no new facts,
and holds no authority. Every number it prints is produced by a module that already
existed and is already separately verifiable; the shell's only contribution is
ordering, aggregation and a single consistent frame.

## What the shell is not

Explicitly, and asserted by tests rather than promised:

1. **Not an authority path.** It cannot open the Consequence Gate, mint a grant,
   widen a ceiling, or approve anything. It may not import `policy.consequence_gate`
   or `policy.engine`, checked by AST.
2. **Not a second planning authority.** It reports the build frontier the blueprint
   computes. It does not rank, schedule, assign or decide. It has no `authorize`,
   `activate`, `schedule`, `execute`, `apply` or `run_action` surface.
3. **Not a writer.** No pipeline stage writes to the repository, the ledger, or any
   external target. The shell takes no output path and no destination argument.
4. **Not a network surface.** It does not listen, dial, or accept a request. An HTTP
   intake is technology #31 and is a separate, unbuilt, founder-gated question.

## Pipeline model

A **Stage** is a name plus a zero-argument callable returning a `StageResult`. Zero
arguments is the load-bearing part: a stage that accepts no input cannot be pointed
at a target, so the shell has no reachable parameter through which an operator or a
caller could turn a report into an action.

A **Pipeline** is a name, a one-line purpose, and an ordered tuple of stages.
Pipelines are declared as data, not assembled at runtime from user input, so the set
of things the shell can do is fixed at import and readable in one file.

Running a pipeline runs each stage in declaration order and collects results. Stages
do not pass values to one another — there is no shared mutable context — so a stage
cannot corrupt a later stage's reading, and any stage can be run alone and give the
same answer.

## Degradation

A stage that raises is reported as `FAILED` with the exception text, and the pipeline
continues. A stage that cannot determine its answer reports `UNRESOLVED` with the
reason. Neither is converted into a number, a default, or silence.

This follows the compiler rule in `UNIIMENTE_FINAL_BUILD_ORDER.md` §4.1: missing
information becomes an explicit unresolved field. An operator surface that hides a
broken reporter is worse than no operator surface, because it manufactures
confidence.

The process exit code reflects the worst outcome across stages, so the shell is
usable in CI without parsing its prose.

## Named pipelines

| Pipeline | Purpose |
|---|---|
| `status` | the default: ladder distribution, organ connectivity, closure coverage |
| `frontier` | what is unblocked right now and who owns it |
| `evidence` | what resolves, what does not, and every unresolved organ question |
| `handoff` | the frozen bundle's integrity and seal |

## What this specification does not deliver

The arsenal declares #14's consequence class as `internal_write`. **This shell writes
nothing.** It is a strict read-only subset of the declared technology, and the
technology is therefore *not* complete when this lands.

The unbuilt remainder — pipelines that perform governed internal writes, such as
recording a decision episode or advancing a workflow state machine — requires the
Consequence Gate on the path and a capability grant per pipeline. That is a larger
change touching the authority path, and it is deliberately out of scope here. The gap
stays recorded in `blueprint/registry.py` under #14 rather than being quietly dropped
once the row stops reading `UNSUPPORTED`.
