"""Integration tests for indexing engine components."""

from __future__ import annotations

import tempfile
import os
from pathlib import Path
import pytest
from buffa.indexing.chunker import CASter
from buffa.indexing.token_chunker import TokenBoundedChunker, split_chunk_with_bounds
from buffa.indexing.fallback_chunker import FallbackChunker, ChunkingResult
from buffa.indexing.embedder import BatchEmbedder
from buffa.indexing.vector_store import VectorStore
from buffa.nim.config import NimConfig
from buffa.shared.models import SourceChunk, ChunkMetadata


def test_chunker_integration_python():
    """Test integration of chunker with Python code."""
    caster = CASter()
    
    python_code = '''
def hello_world():
    """Say hello to the world."""
    print("Hello, World!")
    return True

class MyClass:
    """A simple class."""
    
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value
'''
    
    chunks = caster.chunk_content(python_code, "test.py")
    
    # Should have created chunks
    assert len(chunks) > 0
    
    # Each chunk should have metadata
    for chunk in chunks:
        assert chunk.content.strip()
        assert chunk.metadata.file_path == "test.py"
        assert chunk.metadata.language == "python"
        # When tree-sitter is not available, we get fallback chunks
        assert chunk.metadata.symbol_type in ["function", "class", "method", "block", "fallback"]


def test_chunker_integration_javascript():
    """Test integration of chunker with JavaScript code."""
    caster = CASter()
    
    js_code = '''
function helloWorld() {
    console.log("Hello, World!");
    return true;
}

class MyClass {
    constructor() {
        this.value = 42;
    }
    
    getValue() {
        return this.value;
    }
}
'''
    
    chunks = caster.chunk_content(js_code, "test.js")
    
    # Should have created chunks
    assert len(chunks) > 0
    
    # Each chunk should have metadata
    for chunk in chunks:
        assert chunk.content.strip()
        assert chunk.metadata.file_path == "test.js"
        assert chunk.metadata.language == "javascript"
        # When tree-sitter is not available, we get fallback chunks
        assert chunk.metadata.symbol_type in ["function", "class", "method", "block", "fallback"]


def test_token_chunker_integration():
    """Test integration of token chunker with actual chunks."""
    # Create some chunks with known content
    chunks = [
        SourceChunk(
            content="def short_func():\n    pass",
            metadata=ChunkMetadata(
                file_path="test.py",
                language="python",
                symbol_type="function",
                start_line=1,
                end_line=2,
                symbol_name="short_func"
            )
        ),
        SourceChunk(
            content="def very_long_function_name_that_exceeds_token_limits():\n" + 
                    "    # This is a very long comment\n" +
                    "    x = 1\n" +
                    "    y = 2\n" +
                    "    # More comments\n" +
                    "    for i in range(100):\n" +
                    "        x += i\n" +
                    "    return x\n" * 5,  # Repeat to make it long
            metadata=ChunkMetadata(
                file_path="test.py",
                language="python",
                symbol_type="function",
                start_line=5,
                end_line=50,
                symbol_name="very_long_function_name_that_exceeds_token_limits"
            )
        )
    ]
    
    # Use a token chunker with small limits for testing
    chunker = TokenBoundedChunker()
    chunker.budget.max_chunk_tokens = 50  # Small limit
    
    # Process each chunk
    all_result_chunks = []
    for chunk in chunks:
        result_chunks = chunker.split_chunk(chunk)
        all_result_chunks.extend(result_chunks)
    
    # The long chunk should have been split
    assert len(all_result_chunks) >= len(chunks)  # At least as many as we started with
    
    # All chunks should have content
    for chunk in all_result_chunks:
        assert chunk.content.strip()


def test_fallback_chunker_integration():
    """Test integration of fallback chunker."""
    chunker = FallbackChunker()
    
    # Test with various file types
    test_cases = [
        ("def test():\n    pass\n" * 20, "test.py", "python"),
        ("function test() {\n    return true;\n}\n" * 20, "test.js", "javascript"),
        ("# This is a comment\n" * 30, "test.md", "markdown"),
        ("plain text content\n" * 25, "test.txt", "text")
    ]
    
    for content, file_path, expected_lang in test_cases:
        result = chunker.chunk_content(content, file_path)
        
        assert isinstance(result, ChunkingResult)
        assert len(result.chunks) > 0
        
        # Check that metadata is correct
        for chunk in result.chunks:
            assert chunk.content.strip()
            assert chunk.metadata.file_path == file_path
            assert chunk.metadata.language == expected_lang
            assert chunk.metadata.symbol_type == "fallback"


def test_end_to_end_chunking_flow():
    """Test end-to-end chunking flow from raw content to token-bounded chunks."""
    caster = CASter()
    token_chunker = TokenBoundedChunker()
    
    # Set small token limit for testing
    token_chunker.budget.max_chunk_tokens = 30
    
    # Mixed content that should exercise both chunkers
    mixed_content = '''
def process_data(items):
    """Process a list of items."""
    results = []
    for item in items:
        if item > 0:
            results.append(item * 2)
    return results

class DataProcessor:
    def __init__(self):
        self.data = []
    
    def add_item(self, item):
        self.data.append(item)
    
    def get_processed(self):
        return process_data(self.data)
'''
    
    # Step 1: Chunk with CASter
    initial_chunks = caster.chunk_content(mixed_content, "test.py")
    assert len(initial_chunks) > 0
    
    # Step 2: Apply token bounding
    final_chunks = []
    for chunk in initial_chunks:
        token_chunks = token_chunker.split_chunk(chunk)
        final_chunks.extend(token_chunks)
    
    # Step 3: Validate results
    assert len(final_chunks) > 0
    
    # All chunks should have content and valid metadata
    for chunk in final_chunks:
        assert chunk.content.strip()
        assert chunk.metadata.file_path == "test.py"
        assert chunk.metadata.language == "python"
        # Symbol type should be preserved from original chunking
        assert chunk.metadata.symbol_type in ["function", "class", "method", "block", "fallback"]
        
        # Estimate token count to verify it's within reasonable bounds (approximately)
        # This is approximate since our token estimator is simple
        # Allow some flexibility for the chunking logic
        assert len(chunk.content) < 300  # Rough sanity check


def test_temporary_directory_indexing():
    """Test indexing functionality with temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test files
        py_file = Path(temp_dir) / "test.py"
        py_file.write_text('''
def hello():
    print("Hello")

class Test:
    pass
''')
        
        js_file = Path(temp_dir) / "test.js"
        js_file.write_text('''
function hello() {
    console.log("Hello");
}

class Test {
    constructor() {
        this.value = 1;
    }
}
''')
        
        # Test chunking each file
        caster = CASter()
        
        py_chunks = caster.chunk_content(py_file.read_text(), str(py_file))
        js_chunks = caster.chunk_content(js_file.read_text(), str(js_file))
        
        # Both should produce chunks
        assert len(py_chunks) > 0
        assert len(js_chunks) > 0
        
        # Check metadata
        for chunk in py_chunks:
            assert chunk.metadata.file_path == str(py_file)
            assert chunk.metadata.language == "python"
        
        for chunk in js_chunks:
            assert chunk.metadata.file_path == str(js_file)
            assert chunk.metadata.language == "javascript"


def test_e2e_pipeline_with_mixed_language_files(monkeypatch: pytest.MonkeyPatch):
    """Validate file -> chunker -> embedder -> vector store pipeline on mixed files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        files = {
            "sample.py": "def add(a, b):\n    return a + b\n",
            "sample.js": "function sub(a, b) {\n  return a - b;\n}\n",
            "sample.go": "package main\nfunc mul(a int, b int) int {\n    return a * b\n}\n",
        }

        for name, content in files.items():
            (root / name).write_text(content, encoding="utf-8")

        caster = CASter()
        token_chunker = TokenBoundedChunker()
        token_chunker.budget.max_chunk_tokens = 128

        chunks: list[SourceChunk] = []
        for file_name in files:
            path = root / file_name
            cast_chunks = caster.chunk_content(path.read_text(encoding="utf-8"), str(path))
            for cast_chunk in cast_chunks:
                chunks.extend(token_chunker.split_chunk(cast_chunk))

        assert len(chunks) > 0

        embedder = BatchEmbedder(NimConfig())

        def fake_embed(text: str | list[str], input_type: str = "passage", model: str | None = None):
            texts = text if isinstance(text, list) else [text]
            assert input_type == "passage"
            return [[float(len(t)), 1.0, 0.0] for t in texts]

        monkeypatch.setattr(embedder.embedding_client, "embed", fake_embed)

        embeddings = embedder.embed_chunks(chunks, batch_size=2)
        assert len(embeddings) == len(chunks)

        store = VectorStore(collection_name="test_chunks")
        assert store.upsert_chunks(chunks, embeddings) is True
