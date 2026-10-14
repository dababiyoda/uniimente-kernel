import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def pytest_configure(config):
    config.addinivalue_line("markers", "real_isolation: needs the real worker OS envelope (bubblewrap); skips "
                                       "without it unless GREG_REQUIRE_WORKER_ISOLATION=1")
