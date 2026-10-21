"""Removing fork-safe compilation must fail the process lifecycle regression."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
MUTANTS=[("fork-safe compiler", "config.parallel_compilation = False", "config.parallel_compilation = True")]

def main():
    invalid=0
    with tempfile.TemporaryDirectory(prefix='greg-wasm-mutants-') as temp:
        repo=Path(temp)/'repo'
        shutil.copytree(ROOT,repo,ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache'))
        path=repo/'foundry/systems/wasm.py';original=path.read_text()
        for name,old,new in MUTANTS:
            if original.count(old)!=1:
                print('STALE',name);invalid+=1;continue
            path.write_text(original.replace(old,new))
            run=subprocess.run([sys.executable,'-m','pytest','-q','-x','-p','no:cacheprovider',
                'tests/unit/test_foundry_wasm_lifecycle.py'],cwd=repo,
                env={**os.environ,'PYTHONPATH':str(repo)},capture_output=True,text=True,timeout=45)
            caught=run.returncode==1 and 'FAILED tests/unit/test_foundry_wasm_lifecycle.py::' in run.stdout and 'ERROR collecting' not in run.stdout
            print('CAUGHT' if caught else 'SURVIVED_OR_INVALID',name)
            invalid+=not caught;path.write_text(original)
    return int(bool(invalid))
if __name__=='__main__':raise SystemExit(main())
