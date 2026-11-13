import sys

if sys.version_info < (3, 11):   # stock macOS python3 is 3.9: fail with the fix, not a TypeError deep in an import
    sys.exit(f"GREG needs Python 3.11 or later; this is {sys.version.split()[0]} ({sys.executable}). "
             "Install one (brew install python@3.12, or python.org), then recreate the venv with it: "
             "see greg/FIRST_MISSION.md step 0.")


def _doctor_only(argv: list[str]) -> bool:
    """``doctor --chromebook`` (optionally after ``--home DIR``): the pre-install check runbook step 0 has the founder
    run with the system python3, before any dependency is installed. It must not import the CLI, whose import chain
    needs the installed dependencies (cryptography, rfc3161-client); greg.doctor needs only the standard library."""
    if argv[:1] == ["--home"]:
        argv = argv[2:]
    elif argv[:1] and argv[0].startswith("--home="):
        argv = argv[1:]
    return argv == ["doctor", "--chromebook"]


if _doctor_only(sys.argv[1:]):
    import json  # noqa: E402

    from greg.doctor import chromebook  # noqa: E402
    report = chromebook()
    print(json.dumps(report, indent=1))
    sys.exit(0 if report["ready_for_linux_service"] else 2)

from greg.cli import main  # noqa: E402

sys.exit(main())
