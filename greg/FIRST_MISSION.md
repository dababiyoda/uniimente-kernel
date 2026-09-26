# First mission on the Mac — the VEPMC 0 → 1 runbook

This is for Alfonso, on his own Mac, with his own key. No agent can do these
steps for him. Two of the nine VEPMC conditions (`founder_accepted`, `mac_body`)
cannot be produced by a machine for itself. The other seven were produced by a real
supervised process on Linux (`tests/evidence/greg-body/vepmc-path-summary.json`).

Time: about 30 minutes, plus one overnight wait if you want the morning review
to be real. Cost: $0. External effects: none. The mission writes one file inside
GREG's own workspace, and only after you approve it.

## 0. Before you start

- macOS 13 or later, and Python 3.11 or later (`python3 --version`).
- Clone the kernel **outside** `~/Desktop`, `~/Documents` and `~/Downloads`.
  macOS privacy protection can block a background LaunchAgent from reading those
  folders, and the body would then fail at boot. `~/src` works.
- Optional, as a rehearsal first: `bash greg/mac/verify_mac_body.sh`. It uses a
  throwaway key and a throwaway body, proves launchd restart and stop, and
  cleans up after itself.

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel
git checkout claude/egregore-project-overview-btn5y2
python3 -m venv ~/.uniimente/venv && ~/.uniimente/venv/bin/pip install -r requirements-dev.txt
alias greg="~/.uniimente/venv/bin/python -m greg"
```

## 1. Create the body and your founder key

```bash
greg init --read-root ~/src                            # GREG may read under ~/src, nowhere else
greg founder keygen --key ~/.greg-founder.pem          # choose a real passphrase
greg founder enroll --pubkey <the hex it printed>      # trust on first use; do it yourself
```

The private key never leaves `~/.greg-founder.pem` (mode 0600, passphrase-
encrypted). Every command you send is signed with it. The body refuses anything
unsigned, replayed, expired, or addressed to another body.

## 2. Make it persistent (launchd)

```bash
greg service install --platform macos                 # writes ~/Library/LaunchAgents/ai.uniimente.greg.body.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.uniimente.greg.body.plist
greg status                                           # state RUNNING, with a pid
```

launchd restarts the body after any crash, but not after you stop it (exit 0).
It starts again when you log in. It does not run before login.

## 3. Give it two missions, then close the terminal

```bash
# A real watcher: are the Kernel, DALEOBANKS and WMI pins consistent? Read-only, forever.
greg mission new repo-guardian --repo kernel=$HOME/src/uniimente-kernel \
     --repo dale=$HOME/src/DALEOBANKS --repo wmi=$HOME/src/WealthMachineIntelligence \
     --pin 4999acff1a69502c05af455fbccfca380cad18ee --version 0.1.2 --key ~/.greg-founder.pem

# The VEPMC mission: a bounded write that must stop at your approval.
greg mission new workspace-note --text "the first body is alive" --must-contain alive --key ~/.greg-founder.pem
```

Close every terminal window now. The missions are in the body's inbox and the
body is not attached to any interface.

## 4. Interrupt it on purpose

```bash
greg status                         # note the pid
kill -9 <pid>                       # launchd restarts it within ~10 s
greg status                         # new pid; the history shows body.recovered
```

A stronger test is a full reboot followed by login, then run `greg status` again.

## 5. Answer the approval boundary

```bash
greg decisions                      # one APPROVAL request for write-note, with its reason
greg decide <request_id> approve --key ~/.greg-founder.pem
```

The body writes the note once. The independent appraiser then runs in a separate
process: it re-verifies your signature, re-derives every check from the receipts,
re-reads the file, and confirms the action happened exactly once.

## 6. Morning tribunal and acceptance

```bash
greg morning                        # the 13 questions, answered from evidence
greg vepmc                          # the m:first-note row shows closure_event_id and what is missing
greg accept <closure_event_id> --key ~/.greg-founder.pem
greg vepmc                          # VEPMC: 1, missing: []
```

If you disagree with anything, use `greg critique` instead of `accept`. It is
recorded as new evidence and never rewrites history.

## 7. Stop it (always works)

```bash
greg stop --key ~/.greg-founder.pem        # signed stop; launchd will not restart it
greg stop --local                          # or: physical authority, no key needed
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.uniimente.greg.body.plist
```

## What to send back for the PR

Send `greg vepmc` and `greg morning` output, and `~/.uniimente/greg/ledger.jsonl`
if you are willing to share it. The ledger contains no secrets: the note text,
receipts and hashes only.

## What this does not prove

- It shows possession of your key, not that you personally were at the keyboard.
- It is not a business outcome.
- It shows no computer use beyond files and the read-only repository audit.
- Nothing here authorizes live credentials, spending or publishing.
