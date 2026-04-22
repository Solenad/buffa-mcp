"""Tests for token-bounded chunk splitting."""

from __future__ import annotations

import pytest
import buffa.indexing.token_chunker as token_chunker_module
from buffa.indexing.token_chunker import TokenBoundedChunker, TokenEstimator, split_chunk_with_bounds
from buffa.shared.models import SourceChunk, ChunkMetadata


def test_token_estimator():
    """Test token estimation."""
    estimator = TokenEstimator()
    # Simple test
    tokens = estimator.estimate_tokens("hello world")
    assert isinstance(tokens, int)
    assert tokens > 0


def test_token_estimator_bpe_within_tolerance():
    """Verify estimator stays within +/-20% of model tokenization when BPE is available."""
    estimator = TokenEstimator()
    sample = "def compute_total(items):\n    return sum(item.price for item in items if item.active)\n"

    estimated = estimator.estimate_tokens(sample)
    assert estimated > 0

    if not estimator.using_bpe or token_chunker_module.tiktoken is None:
        pytest.skip("tiktoken not available in current environment")

    encoder = token_chunker_module.tiktoken.get_encoding(estimator.encoding_name)
    actual = len(encoder.encode(sample, disallowed_special=()))
    assert actual > 0

    relative_error = abs(estimated - actual) / actual
    assert relative_error <= 0.20


def test_token_bounded_chunker_no_split_needed():
    """Test chunking when no split is needed."""
    chunker = TokenBoundedChunker()
    chunk = SourceChunk(
        content="short content",
        metadata=ChunkMetadata(
            file_path="test.py",
            language="python",
            symbol_type="function",
            start_line=1,
            end_line=1,
            symbol_name="test_func"
        )
    )
    
    result = chunker.split_chunk(chunk)
    assert len(result) == 1
    assert result[0].content == chunk.content


def test_token_bounded_chunker_splits():
    """Test chunking when split is needed."""
    # Create a chunker with small max tokens for testing
    chunker = TokenBoundedChunker()
    chunker.budget.max_chunk_tokens = 10  # Very small for testing
    
    # Create a long chunk that should be split
    long_content = "def very_long_function_name():\n" + "    pass\n" * 20
    chunk = SourceChunk(
        content=long_content,
        metadata=ChunkMetadata(
            file_path="test.py",
            language="python",
            symbol_type="function",
            start_line=1,
            end_line=21,
            symbol_name="very_long_function_name"
        )
    )
    
    result = chunker.split_chunk(chunk)
    # Should be split into multiple chunks
    assert len(result) > 1
    # All chunks should have content
    for c in result:
        assert c.content.strip()


def test_split_chunk_with_bounds_function():
    """Test the convenience function."""
    chunk = SourceChunk(
        content="test content",
        metadata=ChunkMetadata(
            file_path="test.py",
            language="python",
            symbol_type="function",
            start_line=1,
            end_line=1,
            symbol_name="test_func"
        )
    )
    
    result = split_chunk_with_bounds(chunk)
    assert len(result) == 1
    assert result[0].content == chunk.content
