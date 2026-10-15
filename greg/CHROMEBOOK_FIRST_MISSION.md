# First founder body on Alfonso's Chromebook

The intended first body is the computer Alfonso actually owns. This is a
**developmental** run through ChromeOS's Linux environment (Crostini), not a
claim that it has been run on his Chromebook. The iPhone can become a remote
interface after its transport has been tested on these devices; it cannot
replace the persistent Linux process. No model key, paid API, public posting or
community data is required for this bounded local mission.
Alfonso may later choose a Mac or hardware GREG researches and recommends;
the first-body designation does not appoint that future hardware or authorize
a purchase or migration.

## 0. Check the only hardware prerequisite

On the Chromebook, open **Settings → About ChromeOS → Developers**. If **Linux
development environment** is offered, select **Set up**. If it is disabled by
an administrator or absent, stop: this path has no verified execution body.
Do not enable ChromeOS Developer Mode. Google's Linux setup instructions are
at <https://support.google.com/chromebook/answer/9145439>.

In the Linux Terminal, check `python3 --version` (at least 3.11) and
`git --version`. Debian in the Linux environment ships without the Python venv
package: install it with `sudo apt install python3-venv` (the doctor below reports
it as `python_venv_available`). ARM and Intel Chromebooks both work: every compiled dependency publishes Linux ARM64
and x86-64 wheels for Python 3.11 (checked on PyPI 2026-09-30), so no compiler is needed.
Keep the repository and `~/.uniimente` **inside Linux
files**, not on a shared ChromeOS mount. After cloning below, before creating
any key or body, run `python3 -m greg doctor --chromebook` from the repository.
If it reports `ready_for_linux_service: false`, stop and use its `missing`
checks to diagnose the local runtime. The diagnostic creates no key or body.

## 1. Install the review branch and designate this body

**One command (recommended).** In the Linux terminal:

```bash
sudo apt install -y python3 python3-venv git          # once; skip if already installed
mkdir -p ~/src && cd ~/src
git clone -b claude/uniimente-greg-reconciliation-39syff https://github.com/dababiyoda/uniimente-kernel
cd uniimente-kernel && bash greg/chromebook/install.sh
```

`install.sh` checks that this is ChromeOS Linux, picks Python 3.11+, builds the
venv, writes a `greg` command to `~/.local/bin`, runs the doctor, creates the
body, creates your key (you type the passphrase; the script never sees it),
enrolls it, enables `greg-body.service`, and asks you to sign the designation of
this machine as your first body. Re-running preserves your body, keys, enrollment
and accepted designation. It rewrites the command wrapper and default service
configuration; review any customized service before rerunning. Then skip to step
2. The manual steps below do the same thing by hand.

The installer derives the public key from your actual signing key and checks it
against any companion `.pub` file and the body's current enrollment. A mismatch
stops before service installation or designation; it keeps existing keys and
enrollment intact. To inspect your public key locally, use
`greg founder public --key ~/.greg-founder.pem` (GREG asks for the passphrase).
After an authorized key rotation, use the newly enrolled key. An enabled service
and a queued designation are setup states; inspect `greg status` before a mission.

It also installs GREG's open-source reasoning engines (Z3, OR-Tools, SciPy, NetworkX,
SymPy; about 550 MB, binary wheels only) and prints how many are present. If your
Chromebook has no wheel for one, the install still finishes and that engine is listed as
missing; add `--no-engines` to skip the step. N1 needs none of them.

**Manual install (equivalent):**

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel
git checkout claude/uniimente-greg-reconciliation-39syff   # the one converged GREG branch; use main once merged
python3 -m venv ~/.uniimente/venv
~/.uniimente/venv/bin/pip install -r requirements-dev.txt
~/.uniimente/venv/bin/pip install --only-binary=:all: -r requirements-cognition.txt   # optional engines
alias greg='~/.uniimente/venv/bin/python -m greg'
greg doctor --chromebook                            # stop here if not ready
greg init --read-root ~/src --deliver-root ~/GREG
greg founder keygen --key ~/.greg-founder.pem
greg founder enroll --pubkey <paste the hex printed by keygen>
```

**Optional, before `greg init`:** if Ollama is already running inside this
Chromebook's Linux environment with a model downloaded locally, add
`--local-model '<name-from-ollama-list>'` to `greg init`. Disable Ollama's cloud
features before starting it; see [local cognition](README.md#optional-open-weight-local-cognition).
To let Capability Genesis use that route later, install the service with
`greg service install --platform linux --builder models` in place of the
default service-install command below. The initial repository brief still
works with `--no-model` and no Ollama at all. Do not install or download a
model merely to count the first closure.
After a body exists, use the founder-signed `greg model set --route ollama
--local-model '<downloaded-name>' --key ~/.greg-founder.pem` to replace a
model, or `greg model set --off --key ~/.greg-founder.pem` to detach cognition;
the open console refreshes before the next draft/sign action. Mission state
stays on the same ledger.

Choose your own passphrase; do not give the private key to an agent. Make sure
you recognize the new body ID and that this is the device you intend to use.
The next command queues a founder-signed **designation**, which the body must
accept before your first mission. It does not grant GREG new capabilities or
permissions. Because your key is protected by your passphrase, the same command
also queues a **founder-tier attestation**: the ledger's record that the key
signing your missions is a passphrase-protected founder key, not a test key or a
`--no-passphrase` rehearsal. It grants nothing either. Without it, every closure,
your first one (N1) included, stays a *structural candidate* and never moves
`greg path`. If you rotate
your key, or your body was designated before this existed, run
`greg founder attest --key ~/.greg-founder.pem` once, before signing the missions
that should count.

```bash
greg service install --platform linux
systemctl --user daemon-reload
systemctl --user enable --now greg-body.service
greg body designate --key ~/.greg-founder.pem
greg status
```

The service restarts a crashed GREG process while the Linux VM is running.
ChromeOS does **not** automatically start that VM at login, and sleep can
interrupt work. After a Chromebook restart, open the Linux Terminal to start
the VM, then confirm `greg status`. Closing the Terminal need not close the
VM; test this on your actual machine. ChromeOS background, reboot and power
behavior remain unverified until this run. The official container lifecycle
description is at
<https://www.chromium.org/chromium-os/developer-library/guides/containers/containers-and-vms/>.

## 2. Run and judge one bounded mission

```bash
greg console --key ~/.greg-founder.pem --no-model
```

Open `http://localhost:8766/` in the Chromebook's Chrome browser. ChromeOS
forwards local Linux ports into its browser. Ask **“Brief me on the state of my
repositories.”** Review the proposed read and delivery scope, sign it, then
close the browser tab and press Ctrl-C in the Terminal. The service should
continue. Its brief uses local Git and public GitHub PR data; connectivity is
needed for the latter. See
<https://developers.google.com/chromeos/app-development/develop/web-environment>.

Check `greg status`, note the body PID, and run `kill -9 <body PID>` from the
Terminal. Check again for a new PID and a recovery record. Reopen the console,
approve the **one waiting delivery**, inspect the brief in `~/GREG/briefs/`,
then choose **Accept result** or reject it truthfully. Run:

```bash
greg vepmc
greg morning
greg presence --hours 2
```

If GitHub refused some reads (rate limit, or a private repository), the brief lists
those gaps and GREG asks **once** for access, with the evidence and a no-cost option.
To give it a read-only token: `greg secret set github_token` (you paste it at a hidden
prompt; it stays on this body, never in the ledger; `greg secret remove github_token`
takes it back). Keep the outputs and the brief for review. A ledger row with all nine
conditions is only a **structural candidate**: the ledger cannot prove this
Chromebook is Alfonso's or that Alfonso was physically present. A real founder
run and inspection are required before anyone reports an externally verified
VEPMC increase. A fixture with a test key never counts.

`greg vepmc` keeps `VEPMC` as the compatibility name of `structural_candidate_count`;
each row's `evidence_level` says `STRUCTURAL_CANDIDATE` or, when the mission was signed
with your attested key, `FOUNDER_TIER` (`founder_tier_count`). `greg path` leaves N1
only on a founder-tier closure; a `--no-passphrase` rehearsal that satisfies all nine
ledger checks stays at N1 with `structurally_met: true`. Neither level is an external
verification: the ledger still cannot prove this Chromebook or this key is yours, so
your inspection and acceptance remain the external check. This does not stop the
signed mission runtime or delete later capability nodes.

## After the first closure: the second node (N2), still without a model

If your first closure was signed at the founder tier, `greg path` now shows N2: a closure that
needed a capability GREG did not have. Put a file you
downloaded (with its published SHA-256) under `~/src`, then ask in the console:
**"Verify ~/src/<file> against sha256 <the 64 hex characters>"**. GREG has no hashing
capability, so it finds the installed `sha256sum`, checks it against a frozen oracle before
using it, and verifies the file. Filing the verification record stops for your approval, and
happens only if the digest matches. Interrupt it once with `kill -9` while it waits, approve,
accept the result, then run `greg path` again. A second closure on an unrelated function, e.g.
**"Confirm ~/src/<draft> is at most 1500 words"**, shows the acquisition is not a one-off.

The same route with an open-source engine, if the engines installed: ask
**"Maximize 40 chairs + 30 tables. 2 chairs + 3 tables <= 120. 4 chairs + 2 tables at most 160."**
GREG finds the installed LP engine, shows its version and license, and waits for your Attach.
It then returns the plan with the price of each limit, accepted only on its own duality
certificate.

## The third node (N3): one business case, with you doing every outward act

GREG can now carry one customer case through the Kernel's commercial order (offer, acceptance,
payment, delivery, the buyer's confirmation, settlement) as a mission you sign. Before anything
runs, the signed mission fixes the buyer, the price and the acceptance terms:

```bash
greg mission new business-case --case "lease review 01" --buyer "Acme Property LLC" \
  --offer "a reviewed lease summary" --price 250 --currency USD \
  --acceptance "summary delivered within 5 business days"
```

- GREG drafts `offer.md` in the case folder (`greg status` shows the path). It carries a case
  reference, for example `CASE-LEASE-REVIEW-01`, which the buyer puts on the payment.
- **You** send the offer, collect payment, deliver, and ask the buyer to confirm. Each step is
  one costed ask in the console and on your phone. GREG contacts, charges and pays no one; an
  answer to these asks is only a record.
- You save the evidence into the case folder:
  - `acceptance.txt`: the buyer's written acceptance;
  - `statement.csv`: an export from your payment account. Its columns default to
    `description,amount,currency`; a different export can be mapped in the signed mission.
  - `delivery.txt`: the delivery record;
  - `outcome.txt`: the buyer's confirmation.

  Each file carries the reference.
- **Payment counts only when exactly one posting matches the signed amount and currency to the
  cent and carries the reference.** A short or duplicate payment never counts.
- The settlement record is written only after payment, delivery and the buyer's confirmation
  are all observed. The separate appraiser re-checks that order.

`greg path` measures N3 from the ledger: a founder-signed case on this body, payment reconciled,
every outward step done by a person and observed (a step the person declined does not count),
GREG's own actions internal only and never a write to a file a person's step is measured by (a
statement GREG wrote is not a payment), appraised VERIFIED and
accepted by you, signed with your key at the founder tier (a case signed with a test key or a
`--no-passphrase` rehearsal shows as `structurally_met` with `evidence_level: STRUCTURAL_CANDIDATE`
and never moves the path). Your acceptance is what attests the buyer is real; the ledger cannot prove it.
What no build session can supply: a real buyer and their consent, the legal operator, and your
payment account.

## The fourth node (N4): a procedure you ratify stops costing you attention

After GREG closes the same kind of mission three times (for example three `word-limit` checks),
it proposes a standard procedure. Nothing changes until you ratify it.

```bash
greg sop list                                   # proposals waiting for you, and their inputs
greg sop show <procedure-id>                    # the evidence, the workflow, what may be pre-approved
greg sop ratify <procedure-id> --pre-approve file-record --key ~/greg-founder.pem
greg sop run <procedure-id> --set path="$HOME/drafts/essay.md" --set words=500 --key ~/greg-founder.pem
greg sop trend                                  # before and after, per verified outcome
```

- **The workflow is learned only from what you signed.** It is rebuilt from the verified runs:
  - anything that differed between them becomes an input (above, the file and the limit);
  - checks, capabilities and the light cone must have matched in every run, or no procedure is
    proposed.
- **A run uses no model, and you still sign every run.**
- **`--pre-approve` is limited.** It applies only to steps you approved in every one of those
  runs, internal at most and free:
  - each run you sign names that one step as pre-approved, so it does not stop to ask you;
  - the cone itself is not widened, so every step you did not pre-approve still asks;
  - contact with the outside world and any spend always ask.
- **`greg path` measures N4 from the ledger.** It is met when three runs of the ratified
  procedure:
  - closed on this body, each appraised VERIFIED, none rejected or abandoned;
  - asked you less per verified outcome than the runs that taught it;
  - used no more model spend;
  - and every closure it rests on (the three that taught it and the three runs) was signed at the
    founder tier; otherwise it is a structural candidate only.

## The seventh node (N7): a second venture, and books that pay obligations first

Name the venture on each case. If you want to approve GREG's own writes in a new business, add
`--approve-writes`:

```bash
greg mission new business-case --venture leases --approve-writes --case "lease review 01" ...
```

After three verified cases, ratify the procedure GREG proposes, pre-approving its two writes. Then
run it for a second venture:

```bash
greg sop ratify <procedure-id> --pre-approve draft-offer --pre-approve record-settlement --key ~/greg-founder.pem
greg sop run <procedure-id> --venture audits --set reference=CASE-AUDIT-01 --set buyer="..." \
  --set offer="..." --set price=300.00 --set acceptance="..." --key ~/greg-founder.pem
```

Sign what each venture owes before any surplus counts. Tier names come from
`capital/allocation-policy.yaml`:

```bash
greg treasury set --venture audits --currency USD \
  --tier taxes_and_binding_legal_obligations=120 \
  --tier emergency_liquidity_and_operating_reserves=80 --key ~/greg-founder.pem
greg treasury books
```

- **Revenue counts only from cases that closed N3:** paid to the cent, people did every outward
  act, appraised VERIFIED and accepted by you.
- **Surplus is what remains** after every tier above reinvestment is fully funded.
- **GREG moves and allocates no money;** these are books.
- **`greg path` measures N7.** It is met when a procedure taught by one venture made at least two
  closed cases in another cheaper or faster per outcome, and that venture's books show surplus,
  with every closure that rests on signed at the founder tier.
- **Your judgment remains:** whether the second venture could stand alone.

## The sixth node (N6): one piece of work with a named person

When work needs a person (a designer, a bookkeeper, a lawyer), sign a mission that names them, the
relationship you arrange and pay yourself (`contract` or `employment`), the deliverable and the
acceptance terms:

```bash
greg mission new shared-work --task "Design the GREG logo" --person "Dana Reyes" \
  --relationship contract --function human.design_logo --deliverable logo.png \
  --acceptance "a square PNG, 1024 px, two colors"
```

- GREG writes `handoff.md` first, with the task, the terms, a reference such as
  `WORK-DESIGN-THE-GREG-LOGO` and the person's right to decline. **You** send it; GREG contacts,
  hires and pays no one.
- You save into the case folder, in order:
  - `consent.txt`: their written agreement, carrying the reference;
  - their deliverable;
  - `review.txt`: `ACCEPT <reference>`, or what to revise (the mission waits).

  GREG then writes `outcome.md`.
- **A refusal is honored.** If they decline, save `declined.txt` with the reference:
  - GREG withdraws its ask and never asks that step again;
  - it asks you to choose: name someone else in a new mission, do it yourself, or abandon.

`greg path` measures N6 from the ledger. It needs:

- the handoff written before anything was asked;
- every step of the person's, and your review, observed;
- GREG's own actions internal only;
- the closure appraised VERIFIED and accepted by you;
- the mission signed with your key at the founder tier.

Your acceptance is what attests that the person is real and the relationship lawful; N6's gate stays
external evidence, and the ledger measures only its own side.

## 3. What "persistent" means on this Chromebook

ChromeOS stops the Linux environment when you sign out and, by Google's design,
does not start it again at sign-in; closing the lid suspends it. GREG's missions,
blockers and evidence survive all of that, and the service restarts a crashed
process while Linux runs, but GREG is **not working** while Linux is stopped or
asleep. It does not pretend otherwise:

- `greg presence` (and the first question of `greg morning`, `q0_was_i_present`)
  reports measured availability, every absence with its cause (`process_lost`,
  `os_stop_or_shutdown`, `host_suspended`, `deliberate_stop`) and the due mission
  observations that ran late because of it. Your deliberate stops are not counted
  against availability. The `kill -9` in step 2 appears as one `process_lost`
  absence bounded by the last heartbeat.
- If availability stays below 75% while missions run late, GREG raises **one**
  `BODY_AVAILABILITY` decision with no-spend options first (keep the Chromebook
  signed in and charging; match mission cadence) and, only after that, the option
  of researching always-on hardware you would own. It buys, rents or enrolls
  nothing, and argues from mission lateness, never from its own continuation.

Model cognition is open-source-first: with no selection GREG uses no model at all
(the repository brief needs none). A stored API key or an installed Claude Code
never turns on a paid model; only a route you name in a signed `greg model set`
does.

To stop: `greg stop --local`, then
`systemctl --user stop greg-body.service`. A deliberate stop remains stopped.

The original Mac instructions are retained in [`FIRST_MISSION.md`](FIRST_MISSION.md)
for other environments and historical evidence; no Mac is required here.
