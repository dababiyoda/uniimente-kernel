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
git clone -b codex/greg-vepmc-proof-integrity-20260930 https://github.com/dababiyoda/uniimente-kernel
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

**Manual install (equivalent):**

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel
git checkout codex/greg-vepmc-proof-integrity-20260930    # proof repairs stacked on #137; use main once merged
python3 -m venv ~/.uniimente/venv
~/.uniimente/venv/bin/pip install -r requirements-dev.txt
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
permissions.

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

`greg vepmc` retains `VEPMC` as a compatibility alias for `structural_candidate_count`, labelled `STRUCTURAL_CANDIDATE`. It is not an externally verified closure count. `greg path` stays at N1 even when the rehearsal satisfies all nine ledger checks. Actual founder/body verification still needs appraisal outside this projection; no authenticated import of that external result is implemented yet. This does not stop the signed mission runtime or delete later capability nodes.
