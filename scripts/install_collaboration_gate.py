"""Install the enrolled Claude gate or start a claimed session. No network calls."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import uuid


def safe_path(path):
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError(f'parent traversal refused: {path}')
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError(f"symlink configuration/source refused: {path}")
    return path.resolve()


def settings(repo, workspace, source, install=False):
    repo, workspace, source = map(safe_path, (repo, workspace, source))
    if not repo.is_dir() or not workspace.is_dir() or not repo.is_relative_to(workspace):
        raise ValueError('existing repository inside the shared workspace required')
    gate = safe_path(source / 'scripts/collaboration_gate.py')
    if not gate.is_file() or not (source / 'docs/collaboration/START_HERE.md').is_file():
        raise ValueError('reviewed gate and canonical guide required')
    path = safe_path(repo / '.claude/settings.local.json')
    data = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError('settings must be an object')
    hooks = data.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('hooks must be an object')
    pre = hooks.setdefault('PreToolUse', [])
    if not isinstance(pre, list):
        raise ValueError('PreToolUse must be a list')
    rule = {'matcher': 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'hooks': [{
        'type': 'command', 'command': sys.executable,
        'args': [str(gate), '--workspace', str(workspace), 'hook'],
        'timeout': 10, 'onFailure': 'block'}]}
    # A relocated/edited rule is a conflict, not permission to silently replace it.
    related = [r for r in pre if 'collaboration_gate.py' in json.dumps(r)]
    if related and related != [rule]:
        raise ValueError('existing gate differs; review relocation/configuration manually')
    missing = not related
    if missing and not install:
        raise ValueError('mandatory gate absent; run install before starting a worker')
    if missing:
        pre.append(rule)
        path.parent.mkdir(parents=True, exist_ok=True)
        original = path.read_bytes() if path.exists() else None
        if original is not None:
            backup = safe_path(path.with_name(path.name + '.before-collaboration-gate'))
            with backup.open('xb') as out:
                out.write(original)
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.gate-settings-')
        try:
            with os.fdopen(fd, 'w') as out:
                json.dump(data, out, indent=2)
                out.write('\n')
            os.chmod(temp, mode)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return path, gate


def start(manifest, workspace, source, claude='claude', prompt=None):
    manifest = safe_path(manifest)
    data = json.loads(manifest.read_text())
    session = data['session_id']
    if str(uuid.UUID(session)) != session:
        raise ValueError('Claude launch requires a canonical UUID session_id')
    repo = safe_path(data['repository'])
    config, gate = settings(repo, workspace, source)
    command = [sys.executable, str(gate), '--workspace', str(safe_path(workspace))]
    # Admission must succeed before the client executable can start.
    subprocess.run(command + ['enroll', '--manifest', str(manifest)], check=True)
    instructions = ('Read AGENTS.md and the canonical collaboration guide before work. '
        'Read https://github.com/dababiyoda/uniimente-kernel/discussions/89 and '
        'https://github.com/dababiyoda/uniimente-kernel/issues/96 with current comments. '
        'Honor the admitted bounded claim and release/hand off with evidence.')
    args = [claude, '--session-id', session, '--settings', str(config),
            '--append-system-prompt', instructions]
    if prompt is not None:
        args.extend(['-p', prompt])
    try:
        return subprocess.run(args, cwd=repo).returncode
    finally:
        # Preserve the registry's audit trail. A restart must enroll afresh.
        subprocess.run(command + ['finish', '--session', session], check=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    commands = p.add_subparsers(dest='action', required=True)
    for name in ('install', 'check'):
        commands.add_parser(name).add_argument('--repo', type=Path, required=True)
    run = commands.add_parser('start')
    run.add_argument('--manifest', type=Path, required=True)
    run.add_argument('--claude-bin', default='claude')
    run.add_argument('--prompt', help='Run once in headless print mode; omit for an interactive session')
    a = p.parse_args()
    try:
        if a.action == 'start':
            return start(a.manifest, a.workspace, a.source, a.claude_bin, a.prompt)
        path, _ = settings(a.repo, a.workspace, a.source, a.action == 'install')
        print(f'Collaboration gate configured: {path}')
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f'Collaboration setup refused: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
