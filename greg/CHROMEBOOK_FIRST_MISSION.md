# First founder body on Alfonso's Chromebook

The intended first body is the computer Alfonso actually owns. This is a
**developmental** run through ChromeOS's Linux environment (Crostini), not a
claim that it has been run on his Chromebook. The iPhone can become a remote
interface after its transport has been tested on these devices; it cannot
replace the persistent Linux process. No model key, paid API, public posting or
community data is required for this bounded local mission.

## 0. Check the only hardware prerequisite

On the Chromebook, open **Settings → About ChromeOS → Developers**. If **Linux
development environment** is offered, select **Set up**. If it is disabled by
an administrator or absent, stop: this path has no verified execution body.
Do not enable ChromeOS Developer Mode. Google's Linux setup instructions are
at <https://support.google.com/chromebook/answer/9145439>.

In the Linux Terminal, check `python3 --version` (at least 3.11),
`git --version` and `systemctl --user status`. A missing Python venv package can
be installed through the Debian package manager; a missing `systemd --user`
session needs diagnosis before the service step. Keep the repository and
`~/.uniimente` **inside Linux files**, not on a shared ChromeOS mount.

## 1. Install the review branch and designate this body

```bash
mkdir -p ~/src && cd ~/src
git clone https://github.com/dababiyoda/uniimente-kernel && cd uniimente-kernel
git checkout codex/chromebook-first-body
python3 -m venv ~/.uniimente/venv
~/.uniimente/venv/bin/pip install -r requirements-dev.txt
alias greg='~/.uniimente/venv/bin/python -m greg'
greg init --read-root ~/src --deliver-root ~/GREG
greg founder keygen --key ~/.greg-founder.pem
greg founder enroll --pubkey <paste the hex printed by keygen>
```

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
```

Keep the outputs and the brief for review. A ledger row with all nine
conditions is only a **structural candidate**: the ledger cannot prove this
Chromebook is Alfonso's or that Alfonso was physically present. A real founder
run and inspection are required before anyone reports an externally verified
VEPMC increase. A fixture with a test key never counts.

To stop: `greg stop --local`, then
`systemctl --user stop greg-body.service`. A deliberate stop remains stopped.

The original Mac instructions are retained in [`FIRST_MISSION.md`](FIRST_MISSION.md)
for other environments and historical evidence; no Mac is required here.
