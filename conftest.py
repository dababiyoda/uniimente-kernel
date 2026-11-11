import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# Python modules the computer-use (browser) suites need; GREG_REQUIRE_BROWSER=1 makes their absence a failure.
BROWSER_MODULES = ("playwright",)


def pytest_configure(config):
    config.addinivalue_line("markers", "real_isolation: needs the real worker OS envelope (bubblewrap); skips "
                                       "without it unless GREG_REQUIRE_WORKER_ISOLATION=1")
    if os.environ.get("GREG_REQUIRE_BROWSER") == "1":
        _require_browser()


def _require_browser():
    """The computer-use workflow sets GREG_REQUIRE_BROWSER=1: there ``pytest.importorskip("playwright")`` fails the
    run instead of skipping the browser suites silently. Other optional imports still skip as before."""
    import pytest
    importorskip = pytest.importorskip

    def required(modname, *args, **kwargs):
        try:
            return importorskip(modname, *args, **kwargs)
        except pytest.skip.Exception as exc:
            if modname.partition(".")[0] not in BROWSER_MODULES:
                raise
            pytest.fail(f"GREG_REQUIRE_BROWSER=1 and {exc}", pytrace=False)
    pytest.importorskip = required
