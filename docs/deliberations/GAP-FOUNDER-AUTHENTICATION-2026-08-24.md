# GAP: the institution cannot tell Alfonso from a caller

**Raised:** 2026-08-24, by noticing the same limitation for the third time in
one session rather than by auditing for it.
**Status:** open. Not a defect in any one module; a property of all of them.
**Decision owner:** Alfonso Lopez. Nothing here is actioned without a ruling.

---

## The finding

Four mechanisms now gate a consequential act on **who authorised it**, and
every one of them accepts that authorisation as a string supplied by the
caller. Each was built correctly in isolation. Together they form a single
load-bearing assumption nobody has stated:

| Mechanism | Where | What the string permits |
|---|---|---|
| Constitutional transition | `EvidenceLedger.adopt_constitution(authorized_by=)` | appending to a chain under amended law |
| Autonomy starting grant | `AutonomyAuthority.issue(authorized_by=)` | A1–A8 without the promotion criteria |
| External-action grant | `GrantIssuer.issue_single_action`, called outside the Gate run | an act that reaches outside the institution |
| Constitutional amendment | `governance.integrity.AMENDMENTS` citing a ruling document | moving a watched artifact's authorised hash |

Each refuses `UNIIMENTE` as the authoriser, which is the right rule and closes
the *self*-authorisation case. None can tell **Alfonso** from **any code
holding a reference to the object**.

## Why this is one gap and not four notes

It was written down three separate times, in three docstrings, each honestly —
"process, not cryptography", "attributable, not unforgeable", "the same gap as
a caller issuing its own grant". Three true sentences in three files is how a
structural property stays invisible: every reader sees a local caveat and no
reader sees the shape.

The shape is that **the institution's entire human-authority boundary is
currently a convention among cooperating code.** Every constitutional
protection built so far — deny-by-default, the weakest-link ladder, the
Consequence Gate's refusal to self-grant, the replayed amendment chain —
terminates in a check that a well-formed string was passed.

## What it does and does not mean today

**It is not currently exploitable in any way that matters**, and saying
otherwise would be theatre. Nothing in this repository runs unattended, no
component takes instructions from outside, `CVO` is 0, and every external
pathway is inert. The convention holds because there is exactly one author.

**It becomes load-bearing the moment any of these is true:**

- a Founder Cockpit exists — a surface whose whole purpose is carrying
  Alfonso's commands, where "is this from Alfonso" is the only question that
  matters;
- a standing mandate runs unattended, so no human is present at the moment of
  authorisation;
- a generated or third-party module is loaded, breaking the one-author
  assumption;
- CANARY-0001 or any successor executes externally under a grant.

The first two are items 3 and 4 on the Infinite Goal Chase's own next-work
list. **This gap is upstream of both**, which is why it is being raised now
rather than when one of them is half-built.

## Why this session did not close it

Closing it means choosing how a human proves identity to the institution — a
signing key held by Alfonso, a hardware token, an out-of-band ratification
step, a co-signature quorum, or a deliberate decision that the convention is
adequate at this stage and the risk is accepted. Those differ in what they cost
Alfonso day to day, what happens when the key is lost, and what the institution
does when the human is unavailable.

That is a founder decision about the shape of his own sovereignty. Picking one
unilaterally would be a component deciding how it will recognise its principal,
which has the wrong polarity even when the chosen answer is a good one.

**No mechanism was weakened to raise this.** Every `authorized_by` check
added this session is strictly stronger than the absence it replaced: before
them, a constitutional transition happened silently and A8 was issued against
an empty ledger.

## What would close it

Any of these would be a real answer; they are listed to make the decision
concrete, not to recommend one.

1. **Founder signing key.** `authorized_by` becomes a signature over the act,
   verified against a public key in a constitutional artifact. Strongest, and
   makes key loss an institutional event needing its own recovery procedure.
2. **Out-of-band ratification.** The act is staged and does not take effect
   until confirmed through a separate channel. Weaker cryptographically,
   strong against a compromised process, and slow by design — which for
   constitutional acts may be a feature.
3. **Quorum.** More than one named principal must authorise. Meaningless with
   one author today; the reason to build it early is that adding principals
   later is harder than starting with the shape.
4. **Explicit acceptance.** Record that the convention is adequate at this
   maturity, with the conditions above as the trigger to revisit. This is a
   legitimate answer and is *not* the same as the current state, because the
   current state is unstated.

## Executable record

`tests/unit/test_founder_authentication_gap.py` enumerates every point that
depends on a caller-asserted authoriser and pins the count. A fifth appearing
without a ruling fails the suite. The gap is not allowed to grow quietly while
it waits for a decision.

---

**Nothing here authorises anything.** It is a finding, a decision request, and a
probe. `CVO = 0`, `HARDENED = 0`, and the whole-body verdict remains
`FALSELY_CLOSED`.
