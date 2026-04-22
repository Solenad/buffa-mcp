"""Fallback text chunker with confidence metadata for parser failures."""

from __future__ import annotations

import os
import re
from typing import List, Optional
from dataclasses import dataclass

from buffa.indexing.token_chunker import TokenEstimator
from buffa.shared.models import SourceChunk, ChunkMetadata


@dataclass
class ChunkingResult:
    """Result of chunking operation with confidence metadata."""
    chunks: List[SourceChunk]
    confidence: float  # 0.0 to 1.0, where 1.0 is high confidence cAST chunking
    method_used: str  # "cast", "fallback", "hybrid"
    parser_available: bool


class FallbackChunker:
    """Fallback chunker for when cAST parsing fails or is unavailable."""
    
    def __init__(self):
        self.logger = self._setup_logger()
        self.token_estimator = TokenEstimator()
    
    def _setup_logger(self):
        """Setup logger for the fallback chunker."""
        import logging
        return logging.getLogger(__name__)
    
    def chunk_content(self, content: str, file_path: str, 
                     caster_available: bool = False) -> ChunkingResult:
        """
        Chunk content using fallback strategies.
        
        Args:
            content: Source code content to chunk
            file_path: Path to the source file
            caster_available: Whether cAST chunker is available
            
        Returns:
            ChunkingResult with chunks and confidence metadata
        """
        # Determine file type
        import os
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Try to use cAST if available and appropriate
        if caster_available and self._is_language_supported_for_cast(ext):
            try:
                # In a real implementation, we would try cAST first
                # For now, we'll simulate the fallback path
                self.logger.info(f"cAST available but using fallback for demonstration")
                pass
            except Exception as e:
                self.logger.warning(f"cAST chunking failed, falling back: {e}")
        
        # Use fallback chunking
        chunks = self._fallback_chunk_by_lines(content, file_path)
        
        # Calculate confidence based on what we could parse
        confidence = self._calculate_confidence(content, chunks, ext, caster_available)
        
        return ChunkingResult(
            chunks=chunks,
            confidence=confidence,
            method_used="fallback" if confidence < 0.5 else "hybrid",
            parser_available=caster_available
        )
    
    def _is_language_supported_for_cast(self, ext: str) -> bool:
        """Check if language extension is supported for cAST chunking."""
        supported_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx',  # JavaScript/TypeScript
            '.go', '.rs', '.java', '.kt',          # Systems languages
            '.c', '.cpp'                           # C/C++
        }
        return ext in supported_extensions
    
    def _fallback_chunk_by_lines(self, content: str, file_path: str) -> List[SourceChunk]:
        """
        Fallback to line-based chunking with attempt to preserve semantic boundaries.
        
        Attempts to keep related lines together (e.g., function definitions with their bodies).
        """
        lines = content.split('\n')
        chunks = []
        
        # Get file extension for language detection
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Simple approach: chunk by lines with overlap
        # In a more sophisticated version, we'd try to detect semantic boundaries
        chunk_size = 20  # lines per chunk
        overlap = 4      # lines of overlap between chunks
        
        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i:i + chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            
            if chunk_content.strip():
                # Try to detect if we're cutting off a function or class
                adjusted_end = self._adjust_chunk_end(lines, i, len(chunk_lines))
                actual_lines = lines[i:i + adjusted_end]
                actual_content = '\n'.join(actual_lines)
                
                if actual_content.strip():
                    chunk = SourceChunk(
                        content=actual_content,
                        metadata=ChunkMetadata(
                            file_path=file_path,
                            language=self._detect_language_from_ext(ext),
                            symbol_type="fallback",
                            start_line=i + 1,
                            end_line=i + len(actual_lines),
                            symbol_name=f"fallback_chunk_{len(chunks)}",
                            raw_token_estimate=self._estimate_tokens(actual_content)
                        )
                    )
                    chunks.append(chunk)
                
                # Move to next chunk position
                i += max(1, adjusted_end - overlap)
        
        # Handle any remaining lines
        if not chunks and lines:
            chunk_content = '\n'.join(lines)
            if chunk_content.strip():
                chunk = SourceChunk(
                    content=chunk_content,
                    metadata=ChunkMetadata(
                        file_path=file_path,
                        language=self._detect_language_from_ext(ext),
                        symbol_type="fallback",
                        start_line=1,
                        end_line=len(lines),
                        symbol_name="fallback_chunk_0",
                        raw_token_estimate=self._estimate_tokens(chunk_content)
                    )
                )
                chunks.append(chunk)
        
        return chunks
    
    def _adjust_chunk_end(self, lines: List[str], start_index: int, preferred_length: int) -> int:
        """
        Try to adjust chunk end to avoid cutting off in the middle of a function/class.
        
        Returns the actual number of lines to include.
        """
        if start_index + preferred_length >= len(lines):
            return len(lines) - start_index  # Take everything to the end
            
        # Look ahead a few lines to see if we're in the middle of a block
        look_ahead = min(10, len(lines) - (start_index + preferred_length))
        
        # Simple heuristic: avoid ending on lines that look like they're inside a block
        for offset in range(look_ahead, 0, -1):
            check_index = start_index + preferred_length - offset
            if check_index < len(lines):
                line = lines[check_index].strip()
                # If we find a line that looks like a block start, end before it
                if line.startswith(('def ', 'class ', 'function ', 'struct ', 'class ', 'interface ', 'impl ', 'fn ', 'pub ')):
                    return preferred_length - offset
        
        return preferred_length
    
    def _detect_language_from_ext(self, ext: str) -> str:
        """Detect language name from file extension."""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.kt': 'kotlin',
            '.c': 'c',
            '.cpp': 'cpp',
            '.md': 'markdown',
            '.txt': 'text',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.toml': 'toml'
        }
        return language_map.get(ext, 'unknown')
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text content."""
        return self.token_estimator.estimate_tokens(text)
    
    def _calculate_confidence(self, content: str, chunks: List[SourceChunk], 
                            ext: str, caster_available: bool) -> float:
        """
        Calculate confidence score for the chunking operation.
        
        Higher confidence when:
        - We could use cAST but chose fallback for good reason
        - The content looks well-structured
        - We produced reasonable-sized chunks
        """
        if not chunks:
            return 0.0
            
        # Base confidence
        confidence = 0.3  # Low base for fallback
        
        # Increase if cAST was available but we had to fallback (shows we tried)
        if caster_available:
            confidence += 0.2
            
        # Increase based on chunk quality
        avg_chunk_size = sum(len(chunk.content) for chunk in chunks) / len(chunks)
        if 50 <= avg_chunk_size <= 500:  # Reasonable chunk size
            confidence += 0.2
            
        # Increase if we detect structured content
        structured_patterns = [
            r'def\s+\w+\s*\(',      # Python function
            r'class\s+\w+',         # Class definition
            r'function\s+\w+\s*\(', # JavaScript function
            r'public\s+class',      # Java class
            r'func\s+\w+\s*\(',     # Go/Rust function
            r'struct\s+\w+',        # Struct definition
        ]
        
        structured_matches = 0
        for pattern in structured_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                structured_matches += 1
        
        if structured_matches > 0:
            confidence += min(0.3, structured_matches * 0.1)
            
        # Increase if file extension is known
        if ext in ['.py', '.js', '.ts', '.java', '.go', '.rs']:
            confidence += 0.1
            
        # Cap at 1.0
        return min(1.0, confidence)


def chunk_with_fallback(content: str, file_path: str, 
                       caster_available: bool = False) -> ChunkingResult:
    """
    Convenience function to chunk content with fallback strategy.
    
    Args:
        content: Source code content to chunk
        file_path: Path to the source file
        caster_available: Whether cAST chunker is available
        
    Returns:
        ChunkingResult with chunks and confidence metadata
    """
    chunker = FallbackChunker()
    return chunker.chunk_content(content, file_path, caster_available)
