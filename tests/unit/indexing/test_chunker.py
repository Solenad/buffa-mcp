"""Tests for cAST chunking adapters."""

from __future__ import annotations

import pytest
from buffa.indexing.chunker import CASter, LanguageConfig, get_caster


def test_caster_initialization():
    """Test that CASter initializes correctly."""
    caster = CASter()
    assert caster is not None


def test_get_caster_singleton():
    """Test that get_caster returns the same instance."""
    caster1 = get_caster()
    caster2 = get_caster()
    assert caster1 is caster2


def test_caster_has_language_configs():
    """Test that CASter has language configurations."""
    caster = CASter()
    # Should have configs for common extensions
    assert '.py' in caster.languages
    assert '.js' in caster.languages
    assert '.ts' in caster.languages


def test_fallback_chunking():
    """Test fallback chunking when tree-sitter is not available."""
    caster = CASter()
    # Force fallback by setting TREE_SITTER_AVAILABLE to False
    import buffa.indexing.chunker as chunker_module
    original_available = chunker_module.TREE_SITTER_AVAILABLE
    chunker_module.TREE_SITTER_AVAILABLE = False
    
    try:
        content = "def hello():\n    print('Hello')\n\nclass MyClass:\n    pass"
        chunks = caster.chunk_content(content, "test.py")
        
        # Should have created some chunks
        assert len(chunks) > 0
        # All chunks should have content
        for chunk in chunks:
            assert chunk.content.strip()
    finally:
        # Restore original setting
        chunker_module.TREE_SITTER_AVAILABLE = original_available


def test_parse_and_chunk_from_captures(monkeypatch: pytest.MonkeyPatch):
    """Test that cAST capture nodes are converted into SourceChunk objects."""

    class FakeTree:
        root_node = object()

    class FakeParser:
        def parse(self, source_bytes: bytes):
            return FakeTree()

    class FakeNode:
        def __init__(self, start_byte: int, end_byte: int, start_line: int, end_line: int):
            self.start_byte = start_byte
            self.end_byte = end_byte
            self.start_point = (start_line, 0)
            self.end_point = (end_line, 0)

    caster = CASter()
    content = "def hello():\n    return 1\n\nclass Example:\n    pass\n"

    function_start = content.index("def hello")
    function_end = function_start + len("def hello():\n    return 1")
    class_start = content.index("class Example")
    class_end = class_start + len("class Example:\n    pass")

    function_node = FakeNode(function_start, function_end, 0, 1)
    class_node = FakeNode(class_start, class_end, 3, 4)

    lang_config = LanguageConfig(
        name="python",
        extensions=[".py"],
        parser=FakeParser(),
        query_string="",
        query=object(),
    )

    monkeypatch.setattr(
        caster,
        "_extract_captures",
        lambda _query, _tree: [(function_node, "function"), (class_node, "class")],
    )

    chunks = caster._parse_and_chunk(content, "test.py", lang_config)

    assert len(chunks) == 2
    assert chunks[0].metadata.symbol_type == "function"
    assert chunks[0].metadata.start_line == 1
    assert chunks[1].metadata.symbol_type == "class"
    assert chunks[1].metadata.start_line == 4


def test_chunk_content_fallback_when_parse_raises(monkeypatch: pytest.MonkeyPatch):
    """Test fallback chunking path when parser execution fails."""
    caster = CASter()

    monkeypatch.setattr(caster, "_parse_and_chunk", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("parse failed")))
    monkeypatch.setattr("buffa.indexing.chunker.TREE_SITTER_AVAILABLE", True)

    chunks = caster.chunk_content("def hello():\n    pass\n", "test.py")

    assert len(chunks) > 0
    assert all(chunk.metadata.symbol_type == "fallback" for chunk in chunks)
