"""Fixtures for the WP-03 adapter tests.

Reuses the WP-02 constitution locator so these tests run against the same
five real ``constitution/*.ucl`` files as the UCL suite, wherever the slice
is checked out.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.ucl.conftest import _locate_constitution_dir


@pytest.fixture(scope="session")
def constitution_dir() -> Path:
    """Path to the directory holding the five real .ucl files."""
    return _locate_constitution_dir()
