# What only Alfonso can do (integration candidate #196, 2026-10-22)

Everything else on #196 is agent work. Each item here is a signature, a device interaction or a decision that no
agent may supply. None of them asks you to debug a setup or give anyone a secret.

## 1. Run the first body on your Chromebook (about 30 minutes)

Follow `greg/CHROMEBOOK_FIRST_MISSION.md` sections 0-2. The installer, doctor, supervised rehearsal and acceptance
report pass in the cloud container on this tree (24 tests). That container is not your Chromebook.

1. Turn on **Settings → About ChromeOS → Developers → Linux development environment**. If it is absent or blocked
   by an administrator, stop and say so; that is the finding.
2. In the Linux Terminal, run the commands under "One command (recommended)" in section 1. Choose your own key passphrase when
   asked. Never give the key or the passphrase to an agent.
3. Sign the designation the installer asks for. Then run `greg status`.
4. Section 2: ask the console "Brief me on the state of my repositories", sign it, close the tab, `kill -9` the body
   PID, approve the one waiting delivery, then accept or reject the brief truthfully.
5. Run `greg vepmc`, `greg morning`, `greg presence --hours 2` and `greg acceptance > ~/GREG/acceptance.json`. Send
   back the brief and `acceptance.json`. They contain no secret. `acceptance.json` names the commit you ran.

What it settles: whether VEPMC moves from 0, and what ChromeOS actually does on sleep, reboot and Terminal close.

## 2. Decisions

| # | Decision | Options | Default if you say nothing |
|---|---|---|---|
| D1 | #182: protected Consequence Gate changes | sign them with your enrolled key, or reject | untouched; nothing bypasses the signature |
| D2 | Does a founder-tier closure plus your signed acceptance satisfy N1, or does N1 wait for an external-verification contract? | either | N1 waits |
| D3 | Merge #196 (or any part of it) | merge, request changes, close | no merge |
| D4 | Allow `huggingface.co` and `ollama.com` in this environment's network settings | allow or not | local-model baselines stay NOT_RUN |
| D5 | Attach the admitted CPM genome `solver.or.critical_path` | attach (read-only) or not | withheld; GREG abstains on its own 69-module body package's critical path |
| D6 | The open founder decisions already prepared: D1-D5 in `docs/collaboration/FOUNDER-DECISIONS-2026-10-21.md`, P8 cycle-6 adoption, how `RULE` treats wrong answers | as recorded there | not applied |
| D7 | Where Foundry #9/#10 run (host choice) | name a host | blocked |
| D8 | Post the prepared #193 addendum to Discussion #89 (the GitHub UI; agents have no Discussion write tool) | post or not | not posted |

Nothing here authorizes spending, deployment, outreach or live activation. Each stays separate.
