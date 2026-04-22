from __future__ import annotations


def test_import_scaffold_modules() -> None:
    import buffa.config.runtime  # noqa: F401
    import buffa.indexing  # noqa: F401
    import buffa.retrieval  # noqa: F401
    import buffa.mcp  # noqa: F401
    import buffa.shared.errors  # noqa: F401
