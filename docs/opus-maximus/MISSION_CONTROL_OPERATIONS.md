# Mission Control Operations

Deliverable H. This is the operator card for the founder. The full install path already exists and is not repeated here: `greg/CHROMEBOOK_FIRST_MISSION.md` (Chromebook first body) and `greg/README.md` (commands, phone, anchoring, local model). This card adds what this branch changes, and puts install, security, STOP, rollback and the local model in one place. Nothing here has been run on the founder's Chromebook; the commands were exercised in a Linux container under supervisord.

## 1. Install on the first body

```bash
git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel
git checkout claude/opus-maximus-one-greg-20261014      # this review branch; not main
bash greg/chromebook/install.sh                         # doctor, init, keygen, enroll, service, designate
greg doctor --chromebook                                # must say ready_for_linux_service: true
```

`install.sh` never sees the founder passphrase and is idempotent. If the doctor reports `workers_can_run_confined: false`, install bubblewrap (`sudo apt install -y bubblewrap`) before commissioning any worker.

## 2. One decision this branch asks for at `greg init`: worker confinement

| Choice | What happens | When to choose it |
|---|---|---|
| `--worker-confinement required` (default) | A worker the bubblewrap envelope cannot confine is refused before it starts | Always, unless you need a provider that cannot run in the envelope |
| `--worker-confinement supervised` | Such a worker runs under process supervision instead: own session, killed with the body, scrubbed environment, capped output. Its filesystem and network are **not** confined, and its report says so. It can read any file your user account can, including the founder key if you keep it on this body | Only for a provider you trust with your user account's reach, on a body that holds nothing you would not give it. Keep the founder key on another device |

The setting is written once into the body's private config by your own `greg init`. A hand-edited unknown value runs as `required`. A body that confines egress (`--confined-egress`) refuses supervision rather than let a worker reach the network directly. The script worker always runs in the envelope.

## 3. One opt-in a mission can carry: standing reconciliation

When the body is killed mid-action, GREG never retries blindly; it asks you whether the action executed. A mission you sign may carry:

```json
"standing_reconciliation": {"consequence_inert": true}
```

With it, GREG settles an interruption itself only when it can prove the action could not have left a consequence: a `worker.commission` by the script worker (no network, no credentials, no paid route, writes only inside a private clone discarded before any retry) that left no completed evidence, at most twice per action. The cap held for the interrupted attempt is released, because nothing could have been charged. It records the proof and retries once. Anything else still asks you, and the question lists which conditions failed. Model-drafted mission proposals never carry this field; you add it yourself.

## 4. Daily use

```bash
greg console --key ~/.greg-founder.pem       # Mission Control; open the private link it prints
greg status | greg decisions | greg morning  # read-only views
greg decide <request_id> approve --key ~/.greg-founder.pem
greg vepmc                                   # stays 0 until a closure on this designated body that you accept
```

Mission Control answers five questions from retained events only: what is running, what is waiting for you, what it cost, what was proved, and what changed since yesterday. It was rendered at 1920, 1366 and 390 pixels wide in the ten-step proof.

## 5. STOP

Three ways, strongest last. Each holds while a worker is running.

| Way | Command | Effect |
|---|---|---|
| Signed stop from any enrolled device | `greg stop --key ~/.greg-founder.pem`, or **Stop** on the phone | Authenticated mid-tick, even while a worker runs; the worker's process group is killed |
| Local physical stop | `greg stop --local` | Writes the stop file; the body stops at the next poll and stays stopped across restarts until `greg start --local` |
| Operating system | `systemctl --user stop greg-body.service` | The supervisor stops the body; workers die with it (parent-death signal on Linux) |

After any stop, interrupted actions become UNCERTAIN and wait for your reconciliation (or the standing proof above). Nothing resumes on its own after a deliberate stop.

## 6. Rollback

| What | How | What survives |
|---|---|---|
| This branch's code | `git checkout claude/greg-one-machine` (#178) or any earlier commit, then `systemctl --user restart greg-body.service` | The body directory, ledger, keys and missions. The new config key `worker_confinement` is ignored by older code, which behaves as `required` would for reviewed workers and refuses unreviewed ones |
| The supervisor service | `greg service install --platform linux` rewrites the unit; `systemctl --user disable --now greg-body.service` removes it from startup | Everything in the body directory |
| A mission | `greg pause` or a `LIFECYCLE` abandon, signed | Its history on the ledger |
| A capability | `CAPABILITY_DETACH`, signed | Its registration and evidence |

Never delete the body directory to roll back; the ledger is the institution's memory. Records written by this branch (`route: standing_reconciliation`, the reservation release) stay readable by older code, which counts a standing reconciliation as a failed attempt, exactly as it counts a founder's "not executed".

## 7. Local model (optional)

GREG installs nothing and pulls nothing. If Ollama is already installed with a downloaded model:

1. Disable Ollama's cloud features: `~/.ollama/server.json` containing `{"disable_ollama_cloud": true}`, then restart Ollama.
2. Confirm the model appears in `ollama list` and the API answers on 127.0.0.1:11434.
3. New body: add `--local-model '<name>'` to `greg init`. Existing body: `greg model set --route ollama --local-model '<name>' --key ~/.greg-founder.pem`.
4. Turn it off: `greg model set --off --key ~/.greg-founder.pem`.

No paid route is used unless you sign one with `greg model set`, and a substitute model is used only from a priced allowlist you set.

## 8. Security posture, in one table

| Surface | Protection | Stated limit |
|---|---|---|
| Founder authority | Ed25519 key you hold; nonce, TTL and body binding on every command | A stolen unlocked key is your authority; keep it passphrase-protected and offline |
| Phone | Device key that can only decide, critique, pause, resume, stop, and narrow goals | Expires in at most 90 days; revoke with `greg device revoke` |
| Console | Signs only for its owner session on loopback | Anyone with your local user account can reach loopback |
| Workers | Bubblewrap envelope by default; protected surfaces never accepted; GREG commits, never the worker; no push | `supervised` removes filesystem and network confinement for workers the envelope cannot host; such a worker can read the body's home and a founder key stored there |
| Organs | Own interpreters under Landlock with network denial; signed messages verified at the kernel | One shared HMAC key until the organ pin is upgraded |
| Ledger | Hash-linked, torn tails quarantined; optional RFC 3161 anchoring | Anchoring is off until you sign `ANCHOR_CONFIGURE` |
