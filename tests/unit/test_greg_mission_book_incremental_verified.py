"""The incremental mission book equals a fold from the first event on the verified-answer scenarios too.

#168 (bd0c17dc) made ``MissionBook.rebuild`` fold only new events; the candidate it joined re-derives every answer
from a founder-signed DECISION at its acceptance, holds commands issued before a restore, voids approvals a restore
withdrew and keeps unverifiable rows as data. Those scenarios' own tests are re-run here with every rebuild checked
against a fresh fold (``tests/unit/test_greg_mission_book_incremental.py``'s check, which also compares
``unverified``, ``unverified_requests`` and ``consumed``)."""
import importlib

import pytest

from greg.missions import MissionBook
from tests.unit.test_greg_mission_book_incremental import _original_rebuild, from_the_beginning, view


@pytest.fixture(autouse=True)
def every_rebuild_equals_a_fold_from_the_beginning(monkeypatch):
    """As in test_greg_mission_book_incremental.py, except that a scenario which never rebuilds a book (a reader
    test) is not an error here: it is re-run only to keep the whole module's scenarios in reach."""
    def checked_rebuild(self):
        _original_rebuild(self)
        assert view(self) == view(from_the_beginning(self.journal, getattr(self, "verify_answers", None)))

    monkeypatch.setattr(MissionBook, "rebuild", checked_rebuild)

for _module in ("test_greg_answer_reverification", "test_greg_restore_fold", "test_greg_restore",
                "test_greg_goal_gravity_consumed_approval", "test_greg_reconciliation", "test_greg_goal_gravity",
                "test_greg_human_work", "test_greg_goal_gravity_authority", "test_greg_goal_gravity_reattack"):
    _m = importlib.import_module("tests.unit." + _module)
    for _name in dir(_m):
        _obj = getattr(_m, _name)
        if _name.startswith("test_") and callable(_obj):
            globals()[f"test_{_module[len('test_greg_'):]}__{_name[len('test_'):]}"] = _obj
        elif "fixture" in type(_obj).__name__.lower() and _name not in globals():   # the scenarios' own fixtures
            globals()[_name] = _obj
