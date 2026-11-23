"""The repository's map for newcomers (human or agent) cannot silently drift.

Rules (shared with scripts/repo_review.py, the weekly review):
  * every top-level directory has a README.md and a row in README.md ## Layout;
  * the layout names no directory that does not exist;
  * every top-level file in docs/ is listed in docs/README.md;
  * every entry file defers to AGENTS.md's canonical reading order;
  * of the two case-variant PR templates, the uppercase one names the canonical one.
Each rule is also shown to fire on a planted violation.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("repo_review", ROOT / "scripts" / "repo_review.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def test_every_top_level_directory_has_a_readme():
    assert review.dirs_without_readme(ROOT) == []


def test_every_top_level_directory_is_in_the_readme_layout():
    assert review.dirs_missing_from_layout(ROOT) == []


def test_readme_layout_names_only_real_directories():
    assert review.layout_ghosts(ROOT) == []


def test_docs_index_lists_every_top_level_doc():
    assert review.docs_missing_from_index(ROOT) == []


def test_entry_files_defer_to_one_reading_order():
    assert review.entry_surfaces_not_deferring(ROOT) == []


def test_pr_template_pair_names_its_canonical_member():
    assert review.pr_template_ambiguity(ROOT) == []


def test_whole_review_has_no_hard_findings():
    report = review.build_report(ROOT)
    assert report["hard_finding_count"] == 0, report["hard_findings"]


# ---------------------------------------------------------------- planted violations

@pytest.fixture
def mini(tmp_path):
    """A minimal non-git tree that satisfies every rule."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "README.md").write_text("# pkg\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("`GUIDE.md`\n")
    (tmp_path / "docs" / "GUIDE.md").write_text("# guide\n")
    (tmp_path / "README.md").write_text(
        "> see AGENTS.md#canonical-reading-order\n\n## Layout\n\n| `/pkg` | x |\n| `/docs` | y |\n\n## Next\n")
    (tmp_path / "AGENTS.md").write_text(review.CANONICAL_ORDER_MARKER + "\n")
    for rel in review.ENTRY_SURFACES:
        if rel != "README.md":
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_text("AGENTS.md#canonical-reading-order\n")
    return tmp_path


def test_mini_tree_is_clean(mini):
    report = review.build_report(mini, kept_two_way={}, kept_boundary={}, kept_unwired={})
    assert report["hard_finding_count"] == 0, report["hard_findings"]


def test_new_directory_without_readme_or_row_is_caught(mini):
    (mini / "newthing").mkdir()
    (mini / "newthing" / "x.py").write_text("")
    assert review.dirs_without_readme(mini) == ["newthing"]
    assert review.dirs_missing_from_layout(mini) == ["newthing"]


def test_layout_row_for_missing_directory_is_caught(mini):
    readme = mini / "README.md"
    readme.write_text(readme.read_text().replace("| `/docs` | y |", "| `/docs` | y |\n| `/ghost` | z |"))
    assert review.layout_ghosts(mini) == ["ghost"]


def test_unindexed_doc_is_caught(mini):
    (mini / "docs" / "NEW.md").write_text("# new\n")
    assert review.docs_missing_from_index(mini) == ["NEW.md"]


def test_entry_file_with_its_own_order_is_caught(mini):
    (mini / "CONTRIBUTING.md").write_text("Read these first: 1. X 2. Y\n")
    assert review.entry_surfaces_not_deferring(mini) == ["CONTRIBUTING.md"]


def test_unmarked_template_pair_is_caught(mini):
    gh = mini / ".github"
    (gh / "PULL_REQUEST_TEMPLATE.md").write_text("## Product delta\n")
    (gh / "pull_request_template.md").write_text("## Purpose\n")
    assert review.pr_template_ambiguity(mini) == [".github/PULL_REQUEST_TEMPLATE.md"]


def test_review_workflow_is_read_only_and_never_gates_a_pr():
    import yaml
    wf = yaml.safe_load((ROOT / ".github/workflows/repository-review.yml").read_text())
    triggers = wf.get(True, wf.get("on"))  # PyYAML reads the key `on` as True
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert wf["permissions"] == {"contents": "read", "pull-requests": "read"}
    text = (ROOT / ".github/workflows/repository-review.yml").read_text()
    for forbidden in ("write", "gh issue", "gh pr", "git push", "curl -X POST", "createComment"):
        assert forbidden not in text.split("jobs:", 1)[1], forbidden
