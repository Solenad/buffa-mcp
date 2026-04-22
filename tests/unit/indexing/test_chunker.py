"""Tests for cAST chunking adapters."""

from __future__ import annotations

import pytest
from buffa.indexing.chunker import CASter, get_caster


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