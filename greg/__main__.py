import sys

if sys.version_info < (3, 11):   # stock macOS python3 is 3.9: fail with the fix, not a TypeError deep in an import
    sys.exit(f"GREG needs Python 3.11 or later; this is {sys.version.split()[0]} ({sys.executable}). "
             "Install one (brew install python@3.12, or python.org), then recreate the venv with it: "
             "see greg/FIRST_MISSION.md step 0.")

from greg.cli import main  # noqa: E402

sys.exit(main())
