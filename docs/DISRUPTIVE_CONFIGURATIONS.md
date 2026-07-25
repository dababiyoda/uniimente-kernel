# Disruptive Configurations — Track A

**The institutional capability track. Fourteen recombinations, ordered by ascending audacity. Each one converts a class of failure from *unlikely* to *structurally impossible*.**

Status: research artifact. Not ratified doctrine.

> **Scope, stated up front.** This is one of two tracks. Built alone it produces a governed, self-improving, venture-producing institutional operating system — top-down, authority-bearing, correctness-critical. It does not produce an organ nobody designed, and it must not claim to. The developmental track lives in [`DEVELOPMENTAL_TRACK.md`](./DEVELOPMENTAL_TRACK.md) and runs on its own tests until convergence.
>
> **Vocabulary rule.** Nothing in this document may use developmental language — cell, gradient, differentiation, apoptosis, regeneration — for a mechanism that reads global state. Those terms are reserved for Track B, where each one has a test that can fail. An earlier draft violated this rule by calling a global environment vector a morphogen gradient; the rule exists so that cannot recur.

---

## The spine

Most systems reduce failure probability. That is an asymptote you pay for forever — more tests, more review, more monitoring, and the failure still happens on a long enough timeline.

The interesting move is different: **change the structure so the failure has nowhere to occur.** A garbage-collected language does not have fewer use-after-free bugs. It has none, because the shape of the system does not admit them. That substitution — probability replaced by structure — is what every rung below performs on a different class of institutional failure.

So the ladder reads as a list of things that stop being possible:

| # | Failure that becomes impossible |
|---|---|
| 1 | Losing work to an interruption |
| 2 | Memory that rots as it accumulates |
| 3 | Plans that data already knows are bad |
| 4 | Two agents holding conflicting authority |
| 5 | A safety check that hangs what it protects |
| 6 | Paying model prices forever for deterministic work |
| 7 | Acting faster than you can verify |
| 8 | Dead ventures that keep consuming |
| 9 | Not trying something because trying is expensive |
| 10 | Meeting a governance bug for the first time in production |
| 11 | Being disbelieved by someone who matters |
| 12 | Losing the institution with its infrastructure |
| 13–14 | *speculative — walls named* |

**The method throughout:** take a mechanism from a domain where it is mature and boring, move it to a domain where it is unheard of, and the second domain inherits a decade of hardening for free. Every rung names the mechanism, its original home, and the leap. Where the idea already exists somewhere, I say so — checked prior art is worth more than claimed novelty.

---

# Rung 1 — Work cannot be lost to an interruption
**Weeks · foundational, unglamorous, correct floor**

**Extracted from.** `build your own database` — the **write-ahead log** and its recovery protocol. Durable execution engines (Temporal, Restate, DBOS) generalize the same idea.

**The mechanism.** Write the intent before performing the act. On restart, replay the log and reconcile: anything logged but unfinished is retried; anything finished is skipped. Idempotency keys make replay safe.

**The leap.** The unit of durability is not a database transaction. It is an **agent step**. A process killed mid-workflow — mid-approval, mid-payment, mid-outreach — resumes from its last checkpoint with no human restating what it was doing. Compensations run in reverse order for the steps that did complete.

**Why it's rung 1.** Nobody will be impressed by this, and everything above it is unbuildable without it. A substrate that loses state under interruption cannot be trusted with anything on this list.

**Honest limit.** Idempotency is contagious and easy to get wrong at the boundary. Every external call needs a stable key the *provider* honors, and many providers don't offer one. Where the key is unavailable, you need a reconciliation query instead — and that's per-integration work nobody can abstract away for you.

---

# Rung 2 — Memory cannot rot as it accumulates
**1–2 months**

**Extracted from.** `build your own voxel engine` — the **sparse octree and level-of-detail**. A voxel renderer holds a world larger than memory by keeping full resolution near the viewpoint and progressively coarser representations further out, with seamless transitions between levels.

**The mechanism.** Resolution is a function of distance from the viewpoint. The hierarchy is precomputed; traversal descends only where detail is needed.

**The leap.** Distance is **causal**, not spatial. The viewpoint is the decision currently being made. Events causally adjacent to it are held at full fidelity; distant ones collapse into precomputed summaries; the summary hierarchy is built on write, not generated on demand at query time.

Every memory system in the agent ecosystem — [Mem0](https://github.com/mem0ai/mem0), Zep, Letta — degrades as its corpus grows, because retrieval quality falls when everything is stored at one resolution. LOD is the answer that graphics solved thirty years ago and nobody ported.

**Failure made impossible.** A system that gets worse the longer it runs.

**Honest limit.** Summarization is lossy in a way octree averaging is not — collapsing "the deal failed because legal objected" into "deal failed" destroys the only useful part. Summaries must be *typed* (decision, cause, outcome, counterparty) rather than free-text, so collapse preserves structure. Free-text summarization at scale produces a beautifully organized pile of nothing.

---

# Rung 3 — Plans that data already knows are bad cannot be chosen
**2–3 months**

**Extracted from.** `build your own database` — the **cost-based query optimizer**. Enumerate the plan space, estimate cardinality from maintained statistics, choose minimum estimated cost.

**The mechanism.** The optimizer does not ask what looks reasonable. It costs alternatives against statistics collected from actual execution, and those statistics update continuously.

**The leap.** Action plans get costed against **historical outcome statistics** instead of model intuition. The planner knows that cold email to this segment has a 4% response rate at three-day latency, that this portal times out 20% of the time after 4pm, that this approval path takes nine days when a specific person is on it. It prices the plan accordingly and picks a different one.

Agents today plan greedily and plausibly. A model's sense of "this should work" is not a cardinality estimate, and the gap between them is most of the wasted motion in autonomous systems.

**Failure made impossible.** Repeatedly choosing a strategy your own history has already disproven.

**Honest limit.** Cost-based optimization is only as good as its statistics, and query optimizers famously fall apart on correlated predicates. Yours will too: "email in the morning" and "email this segment" are not independent, and treating them as independent produces confidently wrong estimates. Start with single-dimension histograms, measure estimation error against reality, and expand only where the error justifies it.

---

# Rung 4 — Two agents cannot hold conflicting authority
**3–5 months · this is where it gets interesting**

**Extracted from.** `build your own programming language` — specifically the **type checker**, and from Rust's ownership model: **affine types**, values that may be moved or borrowed but never duplicated.

**Prior art, credited.** This is not a new idea in language design. [Austral](https://austral-lang.org/tutorial/capability-based-security) implements capabilities *as* linear types — consumed on use, surrendered by passing, structurally non-duplicable — and the object-capability model (Dennis & Van Horn) established capabilities as unforgeable tokens decades ago. There is [active 2026 work on capability tracking for agents](https://arxiv.org/pdf/2603.00991).

**The leap.** All of that governs **values inside one program**. Move it to **live authority across a distributed fleet**: a capability grant becomes an affine runtime object with a TTL and a revocation epoch. It can be moved to another agent, or lent for a bounded scope, but never copied. Two agents cannot hold mutable authority over the same resource — not because policy forbids it, but because the grant is not the kind of thing that can exist twice.

The Kernel's Layer 5 capability genomes already carry authority envelopes. This makes the envelope *affine*, and the difference is total: a permission string can be logged, copied, replayed, and leaked. An affine grant cannot.

**Failure made impossible.** The double-commit class — two agents both believing they hold the write. Double payment, double post, double booking, conflicting external commitments made in the same second. This is the failure that makes autonomous fleets unshippable, and it is a *type error*, not a race to be monitored.

**Honest limit.** Affine typing across a network is genuinely hard where the language does not enforce it — you are implementing a distributed ownership protocol, and the failure mode is a grant that gets stranded when its holder dies mid-scope. You need lease expiry as the backstop, which reintroduces a timing assumption. Bound the damage rather than pretending you eliminated it.

---

# Rung 5 — A safety check cannot hang what it protects
**4–6 months**

**Extracted from.** The **eBPF verifier**. Before the Linux kernel loads an eBPF program into its hottest path, a static analyzer proves the program terminates, that every loop has a provably-reached exit, and that every memory access is in bounds. Only then is it JIT-compiled to native code and attached. Cilium runs the Kubernetes datapath this way.

**The mechanism.** *Prove it is safe to run, then run it with near-zero overhead in the most critical path you have.* That inversion is why eBPF changed Linux observability: you can extend a running kernel without trusting the extension and without rebooting.

**The leap.** Policy checks become verified bytecode attached to the agent's execution path. You add a new constraint — "no outbound contact to this counterparty class without a fresh evidence record" — to a **running** substrate, with a proof that it terminates, without a restart and without the possibility that the check itself becomes the outage.

Today, adding a governance rule means a deploy, and a badly written rule can hang the thing it was meant to protect. That's why governance layers are thin: making them richer makes them riskier. The verifier breaks that tradeoff.

**Failure made impossible.** Governance that is unsafe to strengthen.

**Honest limit.** eBPF's verifier is famously conservative — it rejects correct programs, and the [diagnostic quality of rejections is an active research problem](https://arxiv.org/pdf/2607.02748). You will inherit that: expressible policies become a strict subset of desirable policies. Design the policy language for verifiability first and expressiveness second, and accept that some rules must live outside the verified path with a slower, gated execution model.

---

# Rung 6 — Deterministic work cannot stay expensive
**5–9 months · highest practical payoff on this list**

**Extracted from.** `build your own programming language` and modern JS engine architecture: **tiered compilation with deoptimization guards**. Tier 0 interprets. A profiler counts. Hot paths get compiled to native code under *speculative assumptions* — this variable is always an integer, this call site always resolves here — each protected by a **guard**. When a guard fails, execution deoptimizes back to the interpreter, and the path is re-profiled and recompiled.

**Prior art, credited, and the actual distinction.** Semantic caching and model routing exist and work — [reported reductions run 30–70%](https://www.getmaxim.ai/articles/top-semantic-caching-solutions-for-ai-applications-in-2026/) on repetitive workloads, and [tiered LLM caching is under active research](https://arxiv.org/pdf/2602.13165). But caching memoizes **answers**. This promotes **procedures**. A cache returns what was said before; a JIT emits code that computes it, with guards that detect when the assumptions stop holding and fall back. One saves a call. The other removes the model from the path entirely and knows when to put it back.

**The leap.** Tier 0 is a model interpreting a task. The profiler finds paths executed thousands of times with stable structure. Tier 1 emits deterministic code with guards on the assumptions the model was relying on — this field is always present, this vendor always returns this shape, this branch is never taken. A guard trips, execution deoptimizes to the model, and the path recompiles under the new reality.

**Cost per execution falls monotonically with volume,** which is the exact inverse of how agent systems behave today.

**Failure made impossible.** An automation whose unit economics get worse the more you use it.

**Honest limit.** Guard design is the entire problem, and a missing guard is a silent wrong answer rather than a crash — the worst failure shape available. Guard on everything the compiled path assumes, including things that feel too obvious to check, and treat deopt frequency as a first-class metric. A path that never deopts is more likely under-guarded than stable.

---

# Rung 7 — You cannot act faster than you can verify
**6–10 months**

**Extracted from.** `build your own network stack` — **TCP congestion control**. Additive increase, multiplicative decrease. Slow start for new connections. The sender has no view of the network's capacity, so it probes upward gently and retreats hard on the first sign of loss.

**The mechanism.** A control loop that finds a safe operating rate without ever being told what it is.

**The leap.** The congestion signal is **reconciliation lag** — the widening gap between actions taken and outcomes actually verified. Additive increase in the fleet's consequential action rate while verification keeps pace. Multiplicative decrease the instant it falls behind. Slow start for any newly granted capability: it earns throughput by demonstrating its outcomes reconcile.

This is the failure mode of autonomous systems at scale and it has no widely-adopted answer. Agent fleets do not fail by doing one wrong thing. They fail by doing ten thousand things faster than anyone can check, so the error is discovered at volume. Rate limits are the current answer, and rate limits are a fixed guess about a variable quantity. Congestion control is the control-theoretic version, and it has been load-bearing on every network on earth since 1988.

**Failure made impossible.** Discovering a systematic error only after it has been committed at scale.

**Honest limit.** TCP works because loss signals arrive in milliseconds. Reconciliation lag can be days — a slow control loop with long delay oscillates, which is the classic instability. You will need damping and a conservative gain, which means the system runs below its true capacity. That's the correct trade, but say it out loud: this rung deliberately leaves throughput on the table in exchange for never overshooting.

---

# Rung 8 — Dead ventures cannot keep consuming
**9–15 months**

**Extracted from.** `build your own memory allocator` — **generational garbage collection**. The generational hypothesis: most objects die young. So collect the nursery frequently and cheaply; promote survivors to a tenured space collected rarely; use write barriers to track the dangerous case, references from old objects into young ones.

**The leap.** The generational hypothesis is *empirically true of ventures, bets, and commitments*, and nobody has made the analogy operational. New bets live in a nursery with frequent, cheap kill checks. Survivors get promoted and reviewed rarely. Write barriers track the case that actually matters: **a tenured venture that has quietly become dependent on a nursery experiment.** That dependency is invisible in every portfolio review process I know of, and it is exactly how a proven business acquires a fatal dependency on an unproven one.

**The inversion that makes it real.** Collection is automatic. A kill program a human can veto at will is a review meeting with extra steps — it will not fire when it matters, because it never does. So: **termination fires by default; continuation requires affirmative evidence.** A venture that stops meeting its outcome obligations is collected and returns its budget arena unless someone produces a reason it should live.

*(Collection here is centrally scheduled and reads global portfolio state. That makes it garbage collection, not apoptosis — the vocabulary rule above applies to this rung as much as any other.)*

Human sovereignty is completely preserved — the human still decides. What moves is the burden of proof, onto survival, where it belongs. Default-death with affirmative revival is the only portfolio discipline that survives founder attachment, and founder attachment is undefeated.

**Failure made impossible.** The zombie project. The thing everyone privately knows is dead, consuming budget and attention because killing it requires someone to volunteer for the conversation.

**Honest limit.** GC pause semantics have a real analogue: a venture killed mid-commitment leaves external obligations dangling — a customer mid-contract, a counterparty mid-negotiation. You need the equivalent of finalizers, and finalizers are notoriously the worst part of every GC design. Budget for an orderly-wind-down protocol per venture class, and treat the absence of one as a reason a venture cannot enter the nursery at all.

---

# Rung 9 — Trying something cannot be expensive
**12–18 months**

**Extracted from.** `build your own operating system` — **copy-on-write fork**. Plus CRDTs from [Automerge](https://github.com/automerge/automerge) and Yjs: replicas that diverge independently and merge without coordination or conflict resolution.

**The mechanism.** CoW makes duplication nearly free until something is written. CRDTs make independent divergence *safely mergeable* by construction rather than by arbitration.

**The leap.** Fork the **entire institution** — state, memory, policy, capability grants — at near-zero cost. Run the fork against a counterfactual: a different evidence floor, a different capital allocation, a different market posture. Then either discard it or **merge it back**. CRDT-shaped state merges automatically; the state that genuinely conflicts is escalated to a tribunal, and that residue is small.

The Kernel's Institutional Twins already run hermetic forks. This makes fork cost collapse toward zero and, critically, makes the *return path* work. A counterfactual you can only discard teaches you something. One you can merge changes what you do.

**Failure made impossible.** Not exploring an option because exploration is costly — the quiet failure that eliminates most of an organization's upside without ever appearing as a decision anyone made.

**Honest limit.** CRDTs guarantee *convergence*, not *correctness*. Two branches that both allocated the same capital merge to a state that is internally consistent and financially wrong. Anything conserved — money, headcount, a counterparty's attention — is not a CRDT and must be arbitrated explicitly. Know which of your state is which before you build this, or the merge will silently manufacture resources.

---

# Rung 10 — You cannot meet a governance bug for the first time in production
**15–24 months**

**Extracted from.** **Deterministic simulation testing** as practiced by [FoundationDB, TigerBeetle, and madsim](https://github.com/ivanyu/awesome-deterministic-simulation-testing) — every source of nondeterminism made pluggable and seeded, so years of operation simulate in minutes and any failure replays exactly. Plus Erlang/OTP **supervision trees**: let it crash, restart per declared strategy.

**The leap.** Simulate the **institution**, not the service. Clock skew, grants revoked mid-flight, evidence arriving out of causal order, budget races, executor partition, an organ lying. And the model becomes a **recorded oracle** — prompt hash to response, persisted — so replay is bit-exact without pretending a hosted model is deterministic. You stop fighting the one component you cannot control and turn it into a fixture.

TigerBeetle's largest simulation cluster covers roughly two millennia of simulated runtime per day. The Kernel's twelve adversarial gate cases become twelve million, and every failure found is perfectly reproducible.

**Failure made impossible.** Learning your constitution's edge cases from reality.

**Honest limit.** Determinism is all-or-nothing: one unseeded clock read in one organ silently voids the guarantee, and you will not notice. This needs a lint rule and a CI gate from the first commit, because retrofitting it costs multiples of building it in. Rungs 6, 9, and 12 all depend on it, which is why it should be built long before its position here suggests.

---

# Rung 11 — You cannot be disbelieved by someone who matters
**2–3 years · changes the commercial position**

**Extracted from.** [SP1](https://github.com/succinctlabs/sp1) or [RISC Zero](https://github.com/risc0/risc0) — zkVMs proving correct execution of RISC-V programs. [Trillian](https://transparency.dev/) — the append-only tamper-evident log under Sigstore. And [Cedar's verification-guided development](https://arxiv.org/pdf/2407.01688): an authorization engine formally modeled in Lean and Dafny, properties *proven* rather than tested, implementation differentially tested against the model across millions of cases.

**The leap, and why it works here specifically.** Do not prove the computation. Proving model inference is infeasible at useful scale, and chasing it is why verifiable AI remains a poster. **Prove only the gate decision:** given evidence digest E, grant digest G, policy version P, the gate returned ALLOW. A few thousand cycles. Seconds on commodity hardware.

This is available to this Kernel and to almost nobody else, because its founding invariant is that the model **proposes** and the gate **decides**. That architectural split — built for governance reasons, years ago — happens to be exactly the seam that makes zero-knowledge proof tractable. The expensive part is already done.

Every consequential action then ships a succinct proof of authorization plus an inclusion proof that the policy version was public *before* the action. A payer, insurer, regulator, or allocator verifies both in milliseconds with **no access to your evidence, ledger, capital position, or business**.

**Failure made impossible.** Being unable to substantiate what you already do correctly. Every one of those counterparties currently charges you for that gap — as an audit requirement, a risk premium, a compliance narrative, or a relationship you have to maintain.

**Honest limit.** Three, all real. Proving cost scales with circuit size, so the proven statement must stay minimal — the moment someone proposes proving "the whole workflow," the economics collapse. A proof of gate correctness is not a proof of evidence truth: bad evidence yields a valid proof of a bad decision, and you should publish that limitation rather than let a counterparty find it. And log ordering must be witnessed by a third party, or the guarantee is self-referential theater.

---

# Rung 12 — The institution cannot be lost with its infrastructure
**3–5 years**

**Extracted from.** Nix-style **hermetic, reproducible builds**; content addressing from `build your own git`; rung 10's determinism.

**The leap.** The institution as a bit-exact reconstitutable artifact: seed, event log, pinned model oracles, content-addressed capabilities. Rebuildable on hardware that does not exist yet. Continuity as a structural property rather than a disaster-recovery plan — surviving its cloud, its vendors, its stack, and its founder.

**Failure made impossible.** An institution that dies with the company that hosted it.

**The wall, precisely.** You cannot preserve a hosted model — only its transcript. That makes the past replayable but not the future runnable. Full substrate independence requires weights you physically control.

That is not a footnote; it is a strategic conclusion reached from the continuity requirement rather than from fashion. At some point this needs a small model you own outright — not because owned models are better, but because rented cognition is a dependency no amount of governance survives. Worth deciding deliberately rather than discovering during an outage.

---

# Rungs 13–14 — Speculative

Below here I am not confident. Each names its unsolved problem so it can be tracked rather than assumed.

## Rung 13 — Doctrine that cannot be amended into incoherence
**5+ years, partially open research**

Compile the constitution to Lean 4. Every amendment must carry a machine-checked proof that it preserves named invariants: no path to irreversible action without human authority, budget conservation, monotonic provenance.

**Why it isn't fiction.** Cedar proved this method works at policy-language scale.

**The wall.** Verifying a *fixed* specification is solved. Verifying that *every future amendment* preserves property P requires the amendment language be restricted enough that P is inductive over it. Designable; undesigned.

**Available now.** The first slice is not speculative: proving budget conservation and forbid-overrides-permit over the *current* policy set is a Lean exercise of months, using Cedar's published method.

## Rung 14 — Institutions that cannot lie to each other
**Horizon, not roadmap**

Many substrates, each independently provable, interoperating on proofs rather than trust, running cross-institution counterfactuals so a market can rehearse a policy change before adopting it.

**Stated as terminus.** Civilizational claims are where capable engineers go to stop shipping. It is last because treating it as a plan is the most expensive mistake in this document.

---

## Where this actually breaks

Not at rung 14.

**Rung 6 has an unsolved core** — a missing guard produces a silent wrong answer, and no one has a general method for deriving the complete guard set from what a model was implicitly assuming.

**Rung 4 has an unsolved core** — affine ownership across an unreliable network degrades to lease expiry, which is a timing assumption wearing a type system's clothes.

Both arrive far earlier than their position suggests, and everything above them inherits the weakness. That is the honest reading: the difficulty is not at the speculative end, it is in the middle, and it is concentrated in exactly the two rungs that are most worth building.

**The dependency nobody would guess from the ordering:** rung 10 should be built near-first. Deterministic replay is a prerequisite for 6, 9, and 12, it is the cheapest thing on this list to build early, and it is among the most expensive to retrofit. It sits at position 10 because simulating an institution is audacious. It belongs in your first quarter because everything impressive depends on it.

---

## Sources

**Mechanism extraction:** [build-your-own-x](https://github.com/codecrafters-io/build-your-own-x)

**Verified extension & policy:** [What is eBPF](https://ebpf.foundation/what-is-ebpf/) · [Diagnostic gap in eBPF verifier rejections](https://arxiv.org/pdf/2607.02748) · [Cilium use cases](https://phb-crystal-ball.org/cilium-ebpf-use-cases/) · [How We Built Cedar](https://arxiv.org/pdf/2407.01688)

**Capabilities & types:** [Austral: capability-based security via linear types](https://austral-lang.org/tutorial/capability-based-security) · [awesome-ocap](https://github.com/dckc/awesome-ocap) · [Tracking Capabilities for Safer Agents](https://arxiv.org/pdf/2603.00991)

**Cost tiering prior art:** [Top semantic caching solutions 2026](https://www.getmaxim.ai/articles/top-semantic-caching-solutions-for-ai-applications-in-2026/) · [Asynchronous Verified Semantic Caching for Tiered LLM Architectures](https://arxiv.org/pdf/2602.13165) · [Temporal semantic caching in agentic pipelines](https://arxiv.org/pdf/2605.20630)

**Simulation & durability:** [Awesome DST](https://github.com/ivanyu/awesome-deterministic-simulation-testing) · [Antithesis on DST](https://antithesis.com/docs/resources/deterministic_simulation_testing/) · [WarpStream](https://www.warpstream.com/blog/deterministic-simulation-testing-for-our-entire-saas)

**Proof & convergence:** [SP1](https://github.com/succinctlabs/sp1) · [RISC Zero](https://github.com/risc0/risc0) · [Trillian](https://transparency.dev/) · [Automerge](https://github.com/automerge/automerge) · [Local-first / FOSDEM 2026](https://fosdem.org/2026/schedule/track/local-first/)

**Ecosystem context:** [Fungies top-20 agent repos](https://fungies.io/top-github-repositories-ai-agent-frameworks-2026/) · [Firecrawl agent frameworks 2026](https://www.firecrawl.dev/blog/best-open-source-agent-frameworks) · [Agent sandboxing guide](https://manveerc.substack.com/p/ai-agent-sandboxing-guide) · [pyribs / QDax](https://arxiv.org/pdf/2308.03665)
