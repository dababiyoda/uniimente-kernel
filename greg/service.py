"""Supervisor configuration: commodity process managers keep the body alive.

GREG does not implement its own init system. The OS supervisor restarts the
host after a crash (non-zero exit) and leaves it stopped after a deliberate stop
(exit 0). This module only *renders* configuration; installing or loading it is
an explicit founder action (``greg service install --load``), never automatic.

* macOS:  launchd LaunchAgent with RunAtLoad and KeepAlive{SuccessfulExit=false}.
          A signed .app bundle should register the same agent through
          SMAppService (macOS 13+); the plist is identical in substance.
* Linux:  systemd --user unit with Restart=on-failure.
* Any:    supervisord program with autorestart=unexpected, exitcodes=0.
"""
from __future__ import annotations

from pathlib import Path
import plistlib
import sys

LABEL = "ai.uniimente.greg.body"
KERNEL_ROOT = Path(__file__).resolve().parents[1]


BUILDERS = ("none", "claude-code", "models")
# Supervisor-captured stdout/stderr. launchd has no rotator of its own; install()
# also writes logs/greg-logs.rotate for the host's newsyslog or logrotate.
LOG_MAX_BYTES = 1_048_576
LOG_BACKUPS = 3


def _supervisor_logs(home: Path, stem: str) -> str:
    return (
        f"stdout_logfile={home / 'logs' / f'{stem}.out.log'}\n"
        f"stdout_logfile_maxbytes={LOG_MAX_BYTES}\n"
        f"stdout_logfile_backups={LOG_BACKUPS}\n"
        f"stderr_logfile={home / 'logs' / f'{stem}.err.log'}\n"
        f"stderr_logfile_maxbytes={LOG_MAX_BYTES}\n"
        f"stderr_logfile_backups={LOG_BACKUPS}\n"
    )


def log_rotate_config(home: Path) -> str:
    """A logrotate/newsyslog-shaped cap for the four supervisor log files."""
    home = Path(home)
    paths = " ".join(str(home / "logs" / name) for name in (
        "body.out.log", "body.err.log", "remote.out.log", "remote.err.log"))
    return (
        f"{paths}\n"
        "{\n"
        "    rotate 3\n"
        "    size 1M\n"
        "    copytruncate\n"
        "    missingok\n"
        "    notifempty\n"
        "}\n"
    )


def command(home: Path, python: str | None = None, tick_seconds: float = 30, builder: str = "none") -> list[str]:
    if builder not in BUILDERS:
        raise ValueError(f"builder must be one of {BUILDERS}")
    argv = [python or sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", str(tick_seconds)]
    return argv + (["--builder", builder] if builder != "none" else [])


def _path_for_builder(builder: str) -> dict:
    # launchd starts agents with a minimal PATH; a CLI builder route must still find `claude`.
    if builder == "none":
        return {}
    return {"PATH": f"{Path.home() / '.local' / 'bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}


def launchd_plist(home: Path, python: str | None = None, builder: str = "none") -> bytes:
    home = Path(home)
    return plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": command(home, python, builder=builder),
        "WorkingDirectory": str(KERNEL_ROOT),
        "EnvironmentVariables": {"PYTHONPATH": str(KERNEL_ROOT), "PYTHONDONTWRITEBYTECODE": "1",
                                 **_path_for_builder(builder)},
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},   # restart after crash; stay stopped after STOP
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "StandardOutPath": str(home / "logs" / "body.out.log"),
        "StandardErrorPath": str(home / "logs" / "body.err.log"),
    })


def systemd_unit(home: Path, python: str | None = None, builder: str = "none") -> str:
    args = " ".join(command(Path(home), python, builder=builder))
    return (
        "[Unit]\nDescription=UNIIMENTE GREG body (persistent personal agentic operating layer)\n"
        "After=network-online.target\n\n"
        "[Service]\nType=simple\n"
        f"WorkingDirectory={KERNEL_ROOT}\nEnvironment=PYTHONPATH={KERNEL_ROOT}\n"
        f"ExecStart={args}\n"
        "Restart=on-failure\nRestartSec=5\nKillSignal=SIGTERM\nTimeoutStopSec=30\n"
        "NoNewPrivileges=true\n\n[Install]\nWantedBy=default.target\n")


def supervisord_program(home: Path, python: str | None = None, *, name: str = "greg-body",
                        tick_seconds: float = 30, builder: str = "none") -> str:
    home = Path(home)
    return (
        f"[program:{name}]\n"
        f"command={' '.join(command(home, python, tick_seconds, builder))}\n"
        f"directory={KERNEL_ROOT}\n"
        f"environment=PYTHONPATH=\"{KERNEL_ROOT}\",PYTHONDONTWRITEBYTECODE=\"1\"\n"
        "autostart=true\nautorestart=unexpected\nexitcodes=0\nstartsecs=1\nstartretries=100\n"
        "stopsignal=TERM\nstopwaitsecs=30\n"
        + _supervisor_logs(home, "body"))


REMOTE_LABEL = "ai.uniimente.greg.remote"


def remote_command(home: Path, python: str | None = None, port: int = 8765) -> list[str]:
    return [python or sys.executable, "-m", "greg", "--home", str(home), "serve", "--port", str(port)]


def launchd_remote_plist(home: Path, python: str | None = None, port: int = 8765) -> bytes:
    """The phone's channel, kept alive like the body. It holds no key and writes no history,
    so it always restarts; stop it with launchctl bootout."""
    home = Path(home)
    return plistlib.dumps({
        "Label": REMOTE_LABEL, "ProgramArguments": remote_command(home, python, port),
        "WorkingDirectory": str(KERNEL_ROOT),
        "EnvironmentVariables": {"PYTHONPATH": str(KERNEL_ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
        "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 10, "ProcessType": "Background",
        "StandardOutPath": str(home / "logs" / "remote.out.log"),
        "StandardErrorPath": str(home / "logs" / "remote.err.log"),
    })


def install(home: Path, platform: str, *, target_dir: Path | None = None, remote: bool = False,
            builder: str = "none") -> Path:
    """Write (but do not load) the supervisor file. Loading is a separate founder step."""
    home = Path(home)
    (home / "logs").mkdir(parents=True, exist_ok=True)
    (home / "logs" / "greg-logs.rotate").write_text(log_rotate_config(home))
    if remote:
        if platform == "macos":
            target = (target_dir or Path.home() / "Library" / "LaunchAgents") / f"{REMOTE_LABEL}.plist"
            data = launchd_remote_plist(home)
        elif platform == "linux":
            target = (target_dir or Path.home() / ".config" / "systemd" / "user") / "greg-remote.service"
            data = ("[Unit]\nDescription=GREG remote channel (loopback)\n\n[Service]\nType=simple\n"
                    f"WorkingDirectory={KERNEL_ROOT}\nEnvironment=PYTHONPATH={KERNEL_ROOT}\n"
                    f"ExecStart={' '.join(remote_command(home))}\nRestart=always\nRestartSec=5\n"
                    "NoNewPrivileges=true\n\n[Install]\nWantedBy=default.target\n").encode()
        elif platform == "supervisord":
            target = (target_dir or home) / "supervisord-greg-remote.conf"
            data = (f"[program:greg-remote]\ncommand={' '.join(remote_command(home))}\ndirectory={KERNEL_ROOT}\n"
                    f"environment=PYTHONPATH=\"{KERNEL_ROOT}\"\nautostart=true\nautorestart=true\n"
                    + _supervisor_logs(home, "remote")).encode()
        else:
            raise ValueError("platform must be macos, linux or supervisord")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target
    if platform == "macos":
        target = (target_dir or Path.home() / "Library" / "LaunchAgents") / f"{LABEL}.plist"
        data = launchd_plist(home, builder=builder)
    elif platform == "linux":
        target = (target_dir or Path.home() / ".config" / "systemd" / "user") / "greg-body.service"
        data = systemd_unit(home, builder=builder).encode()
    elif platform == "supervisord":
        target = (target_dir or home) / "supervisord-greg.conf"
        data = supervisord_program(home, builder=builder).encode()
    else:
        raise ValueError("platform must be macos, linux or supervisord")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def load_instructions(platform: str, path: Path) -> str:
    return {
        "macos": f"launchctl bootstrap gui/$(id -u) {path}   # stop: launchctl bootout gui/$(id -u) {path}",
        "linux": "systemctl --user daemon-reload && systemctl --user enable --now greg-body.service",
        "supervisord": f"supervisord -c <your supervisord.conf including {path}>",
    }[platform]
