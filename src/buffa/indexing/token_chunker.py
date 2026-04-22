"""Token-bounded chunk splitting with provenance metadata preservation."""

from __future__ import annotations

import re
from typing import Any, List, Optional
from dataclasses import dataclass

from buffa.shared.models import SourceChunk, ChunkMetadata


try:
    import tiktoken
except ImportError:  # pragma: no cover - exercised in environments without tiktoken
    tiktoken = None


@dataclass
class TokenBudget:
    """Configuration for token budgeting in chunking."""
    max_chunk_tokens: int = 512
    min_chunk_tokens: int = 20
    overlap_tokens: int = 32


class TokenEstimator:
    """Model-aware token estimator for text content."""

    _encoder_cache: dict[str, Any] = {}

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self.encoding_name = encoding_name
        self._encoder = self._load_encoder(encoding_name)
        self.using_bpe = self._encoder is not None

    @classmethod
    def _load_encoder(cls, encoding_name: str) -> Any:
        """Load and cache a tokenizer encoder."""
        if encoding_name in cls._encoder_cache:
            return cls._encoder_cache[encoding_name]

        if tiktoken is None:
            cls._encoder_cache[encoding_name] = None
            return None

        try:
            encoder = tiktoken.get_encoding(encoding_name)
        except Exception:
            encoder = None

        cls._encoder_cache[encoding_name] = encoder
        return encoder

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        if self._encoder is not None:
            return len(self._encoder.encode(text, disallowed_special=()))

        # Fallback approximation for environments without tiktoken.
        words = re.findall(r'\b\w+\b', text)
        return int(len(words) * 1.3)


class TokenBoundedChunker:
    """Chunks content to fit within token boundaries while preserving metadata."""
    
    def __init__(self, budget: Optional[TokenBudget] = None, estimator: Optional[TokenEstimator] = None) -> None:
        self.budget = budget or TokenBudget()
        self.token_estimator = estimator or TokenEstimator()
    
    def split_chunk(self, chunk: SourceChunk) -> List[SourceChunk]:
        """
        Split a chunk into smaller pieces that fit within token budget.
        
        Args:
            chunk: SourceChunk to potentially split
            
        Returns:
            List of SourceChunk objects, each within token budget
        """
        # Estimate tokens in the original chunk
        estimated_tokens = self.token_estimator.estimate_tokens(chunk.content)
        
        # If already within budget, return as-is
        if estimated_tokens <= self.budget.max_chunk_tokens:
            return [chunk]
            
        # If below minimum, we still return it (but could log warning)
        if estimated_tokens < self.budget.min_chunk_tokens:
            return [chunk]
            
        # Need to split the chunk
        return self._split_by_lines(chunk)
    
    def _split_by_lines(self, chunk: SourceChunk) -> List[SourceChunk]:
        """
        Split chunk by lines to respect token boundaries.
        
        Attempts to keep semantic units together where possible.
        """
        lines = chunk.content.split('\n')
        chunks = []
        
        current_lines = []
        current_start_line = chunk.metadata.start_line
        current_token_count = 0
        
        for i, line in enumerate(lines):
            line_tokens = self.token_estimator.estimate_tokens(line)
            
            # If adding this line would exceed max budget and we have content
            if current_token_count + line_tokens > self.budget.max_chunk_tokens and current_lines:
                # Create chunk from current lines
                chunk_content = '\n'.join(current_lines)
                if chunk_content.strip():  # Only add non-empty chunks
                    new_chunk = SourceChunk(
                        content=chunk_content,
                        metadata=ChunkMetadata(
                            file_path=chunk.metadata.file_path,
                            language=chunk.metadata.language,
                            symbol_type=chunk.metadata.symbol_type,
                            start_line=current_start_line,
                            end_line=current_start_line + len(current_lines) - 1,
                            symbol_name=f"{chunk.metadata.symbol_name}_part_{len(chunks)}",
                            hash=chunk.metadata.hash,
                            raw_token_estimate=current_token_count
                        )
                    )
                    chunks.append(new_chunk)
                
                # Start new chunk with overlap
                overlap_lines = []
                overlap_token_count = 0
                # Add lines from the end of current chunk for overlap
                for j in range(len(current_lines) - 1, max(-1, len(current_lines) - self.budget.overlap_tokens - 1), -1):
                    if j >= 0:
                        overlap_line = current_lines[j]
                        overlap_line_tokens = self.token_estimator.estimate_tokens(overlap_line)
                        if overlap_token_count + overlap_line_tokens <= self.budget.overlap_tokens:
                            overlap_lines.insert(0, overlap_line)
                            overlap_token_count += overlap_line_tokens
                        else:
                            break
                
                current_lines = overlap_lines + [line]
                current_start_line = chunk.metadata.start_line + i - len(overlap_lines)
                current_token_count = overlap_token_count + line_tokens
            else:
                current_lines.append(line)
                current_token_count += line_tokens
        
        # Don't forget the last chunk
        if current_lines:
            chunk_content = '\n'.join(current_lines)
            if chunk_content.strip():
                new_chunk = SourceChunk(
                    content=chunk_content,
                    metadata=ChunkMetadata(
                        file_path=chunk.metadata.file_path,
                        language=chunk.metadata.language,
                        symbol_type=chunk.metadata.symbol_type,
                        start_line=current_start_line,
                        end_line=current_start_line + len(current_lines) - 1,
                        symbol_name=f"{chunk.metadata.symbol_name}_part_{len(chunks)}",
                        hash=chunk.metadata.hash,
                        raw_token_estimate=current_token_count
                    )
                )
                chunks.append(new_chunk)
                
        return chunks if chunks else [chunk]  # Fallback to original if something went wrong


def split_chunk_with_bounds(chunk: SourceChunk, budget: Optional[TokenBudget] = None) -> List[SourceChunk]:
    """
    Convenience function to split a chunk with token boundaries.
    
    Args:
        chunk: SourceChunk to split
        budget: Optional token budget configuration
        
    Returns:
        List of SourceChunk objects within token bounds
    """
    chunker = TokenBoundedChunker(budget)
    return chunker.split_chunk(chunk)
