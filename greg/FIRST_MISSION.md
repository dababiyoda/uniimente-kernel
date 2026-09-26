# First mission on the Mac — the VEPMC 0 → 1 runbook

This is for Alfonso, on his own Mac, with his own key. No agent can do these
steps for him: two of the nine VEPMC conditions (`founder_accepted`, `mac_body`)
cannot be produced by a machine for itself. The other seven were produced by a real
supervised process on Linux, through this same path
(`tests/evidence/greg-product/product-path-summary.json`, and on real repositories
with live GitHub: `live-real-repos-summary.json`).

Time: about 30 minutes. Cost: $0. External effects: none. GREG reads your local
checkouts and public pull-request data, and writes one brief into a folder you choose,
only after you approve it.

## 0. Before you start

- macOS 13 or later, Python 3.11 or later (`python3 --version`), Git.
- Clone the kernel **outside** `~/Desktop`, `~/Documents` and `~/Downloads` (macOS privacy
  protection can block a background LaunchAgent there). `~/src` works. Put the repositories
  you want briefed under the same folder, e.g. `~/src/DALEOBANKS`.
- Optional rehearsal first: `bash greg/mac/verify_mac_body.sh` (throwaway key and body).

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel
git checkout claude/greg-persistent-mission-build-t0vqu7
python3 -m venv ~/.uniimente/venv && ~/.uniimente/venv/bin/pip install -r requirements-dev.txt
alias greg="~/.uniimente/venv/bin/python -m greg"
```

## 1. Create the body and your founder key

```bash
greg init --read-root ~/src --deliver-root ~/GREG     # reads under ~/src; delivers into ~/GREG
greg founder keygen --key ~/.greg-founder.pem          # choose a real passphrase
greg founder enroll --pubkey <the hex it printed>      # trust on first use; do it yourself
```

Optional: a GitHub token raises the rate limit from 60 to 5,000 calls an hour. Store it in
the login Keychain yourself; GREG only ever reads it by name:
`security add-generic-password -s uniimente.greg -a github_token -w <token>`.

## 2. Make it persistent (launchd)

```bash
greg service install --platform macos
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.uniimente.greg.body.plist
greg status                                           # background state RUNNING, with a pid
```

launchd restarts the body after any crash, not after you stop it, and starts it at login.

## 3. Ask GREG, sign, close the window

```bash
greg console --key ~/.greg-founder.pem --no-model     # http://127.0.0.1:8765
```

In the browser, type: *"Brief me on the state of my repositories."* Review the proposal:
it lists exactly what GREG may do without asking (observe its brief folder) and what it must
ask first (deliver the brief). Click **Sign and send**, then close the tab and press Ctrl-C.
The body keeps working; nothing needs to stay open.

(`--no-model` plans with templates only. Without it, requests no template covers are drafted
by your installed Claude Code, vetted, clamped to read-only and shown to you before signing.)

## 4. Interrupt it on purpose

```bash
greg status                         # note the pid
kill -9 <pid>                       # launchd restarts it within ~10 s
greg status                         # new pid; history shows body.recovered
```

A stronger test is a full reboot and login, then `greg status` again. A write torn by a power
cut is quarantined next to the ledger, never replayed and never lost.

## 5. Approve, read, accept

```bash
greg console --key ~/.greg-founder.pem --no-model
```

Approve the one waiting decision. Within a tick GREG writes exactly one brief to
`~/GREG/briefs/`, and a separate process appraises it: it re-verifies your signature,
re-renders the brief from the receipted inputs and byte-compares the file, and confirms the
action ran once. Open the brief from **Deliveries**. If it is right, click **Accept result**.

```bash
greg vepmc                          # VEPMC: 1, missing: []   (on the Mac, after your acceptance)
```

To have it every morning instead: *"Every morning brief me on my repositories"*. You approve
the delivery once; the same exact scope is reused each day and nothing is ever overwritten.

## 6. Stop it (always works)

Console **Stop GREG**, or `greg stop --key ~/.greg-founder.pem`, or `greg stop --local`
(no key needed). Then `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.uniimente.greg.body.plist`.

## What to send back for the PR

`greg vepmc` and `greg morning` output, and `~/.uniimente/greg/ledger.jsonl` if you are willing
to share it (receipts, hashes, repository metadata; no secrets).

## What this does not prove

- Possession of your key, not that you personally were at the keyboard.
- Not a business outcome; not computer use beyond files, Git and a public API.
- Nothing here authorizes live credentials beyond an optional read-only token, spending or publishing.
