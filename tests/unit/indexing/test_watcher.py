"""Tests for Git watcher branch diff caching behavior."""

from __future__ import annotations

from types import SimpleNamespace

from buffa.indexing.watcher import GitBranchWatcher, IndexingWatcher, WatchConfig


def test_git_branch_watcher_caches_diff(monkeypatch) -> None:
    """Repeated branch diff requests should use cache after first call."""
    run_calls = {"count": 0}

    def fake_run(_args, capture_output, text, timeout):  # noqa: ANN001
        run_calls["count"] += 1
        return SimpleNamespace(returncode=0, stdout="src/a.py\nsrc/b.py\n")

    monkeypatch.setattr("buffa.indexing.watcher.subprocess.run", fake_run)

    watcher = GitBranchWatcher(callback=lambda _old, _new: None)

    first = watcher.get_changed_files_between("main", "feature")
    second = watcher.get_changed_files_between("main", "feature")

    assert first == {"src/a.py", "src/b.py"}
    assert second == {"src/a.py", "src/b.py"}
    assert run_calls["count"] == 1


def test_indexing_watcher_invalidate_cache_on_file_changes(monkeypatch) -> None:
    """File-system changes invalidate cached git diff state."""
    invalidate_calls = {"count": 0}

    watcher = IndexingWatcher(index_callback=lambda _files: None, config=WatchConfig(enabled=False))
    watcher.git_watcher = GitBranchWatcher(callback=lambda _old, _new: None)

    def fake_invalidate() -> None:
        invalidate_calls["count"] += 1

    monkeypatch.setattr(watcher.git_watcher, "invalidate_cache", fake_invalidate)

    watcher._on_file_changes({"src/example.py"})

    assert invalidate_calls["count"] == 1


def test_on_git_branch_change_uses_cached_diff(monkeypatch) -> None:
    """Branch change handler should use GitBranchWatcher cached diff accessor."""
    indexed: list[set[str]] = []

    watcher = IndexingWatcher(
        index_callback=lambda files: indexed.append(set(files)),
        config=WatchConfig(enabled=False, on_git_branch_switch="reindex_changed"),
    )
    watcher.git_watcher = GitBranchWatcher(callback=lambda _old, _new: None)

    monkeypatch.setattr(
        watcher.git_watcher,
        "get_changed_files_between",
        lambda _old, _new: {"src/changed.py"},
    )

    watcher._on_git_branch_change("main", "feature")

    assert indexed == [{"src/changed.py"}]
