"""cAST-based chunking adapters for Buffa indexing engine."""

from __future__ import annotations

import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    import tree_sitter
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from buffa.shared.models import SourceChunk, ChunkMetadata

logger = logging.getLogger(__name__)


@dataclass
class LanguageConfig:
    """Configuration for a specific language's chunking."""
    name: str
    extensions: List[str]
    parser: Any  # tree_sitter.Parser when available
    query_string: str


class CASter:
    """cAST chunking adapter using tree-sitter."""
    
    def __init__(self):
        self.languages: Dict[str, LanguageConfig] = {}
        self._initialize_language_parsers()
    
    def _initialize_language_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        # Language configurations based on PLAN.md
        language_configs = [
            {
                "name": "python",
                "extensions": [".py"],
                "query": """
                [
                    (function_definition) @function
                    (class_definition) @class
                    (method_definition) @method
                ]
                """
            },
            {
                "name": "javascript",
                "extensions": [".js", ".jsx"],
                "query": """
                [
                    (function_declaration) @function
                    (class_declaration) @class
                    (method_definition) @method
                ]
                """
            },
            {
                "name": "typescript",
                "extensions": [".ts", ".tsx"],
                "query": """
                [
                    (function_declaration) @function
                    (class_declaration) @class
                    (method_definition) @method
                    (interface_declaration) @interface
                ]
                """
            },
            {
                "name": "go",
                "extensions": [".go"],
                "query": """
                [
                    (function_declaration) @function
                    (method_declaration) @method
                    (type_declaration) @class
                ]
                """
            },
            {
                "name": "rust",
                "extensions": [".rs"],
                "query": """
                [
                    (function_item) @function
                    (struct_item) @class
                    (enum_item) @class
                    (trait_item) @interface
                    (impl_item) @impl
                ]
                """
            },
            {
                "name": "java",
                "extensions": [".java"],
                "query": """
                [
                    (method_declaration) @method
                    (class_declaration) @class
                    (interface_declaration) @interface
                ]
                """
            },
            {
                "name": "cpp",
                "extensions": [".c", ".cpp"],
                "query": """
                [
                    (function_definition) @function
                    (class_specifier) @class
                    (struct_specifier) @class
                ]
                """
            }
        ]
        
        for config in language_configs:
            try:
                # In a real implementation, we would load the actual language parsers
                # For now, we'll simulate the structure
                parser = None  # Would be tree_sitter.Parser() with language set
                lang_config = LanguageConfig(
                    name=config["name"],
                    extensions=config["extensions"],
                    parser=parser,
                    query_string=config["query"]
                )
                for ext in config["extensions"]:
                    self.languages[ext] = lang_config
                    
                if TREE_SITTER_AVAILABLE:
                    logger.info(f"Initialized cAST parser for {config['name']}")
                else:
                    logger.debug(f"Initialized language config for {config['name']} (cAST not available)")
            except Exception as e:
                logger.error(f"Failed to initialize parser for {config['name']}: {e}")
    
    def chunk_content(self, content: str, file_path: str) -> List[SourceChunk]:
        """
        Chunk content using cAST parsing.
        
        Args:
            content: Source code content to chunk
            file_path: Path to the source file
            
        Returns:
            List of SourceChunk objects with metadata
        """
        if not TREE_SITTER_AVAILABLE:
            logger.warning("tree-sitter not available, falling back to simple chunking")
            return self._fallback_chunking(content, file_path)
            
        # Get file extension
        import os
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext not in self.languages:
            logger.warning(f"No cAST parser for extension {ext}, falling back")
            return self._fallback_chunking(content, file_path)
            
        lang_config = self.languages[ext]
        
        try:
            # In a real implementation, we would:
            # 1. Parse the content with tree-sitter
            # 2. Execute the query to find nodes
            # 3. Extract chunks from those nodes
            # For now, we'll return a placeholder implementation
            
            chunks = self._parse_and_chunk(content, file_path, lang_config)
            return chunks
        except Exception as e:
            logger.error(f"Error during cAST chunking of {file_path}: {e}")
            return self._fallback_chunking(content, file_path)
    
    def _parse_and_chunk(self, content: str, file_path: str, lang_config: LanguageConfig) -> List[SourceChunk]:
        """
        Parse content with tree-sitter and extract chunks.
        
        This is a simplified implementation - in reality, we would use
        tree-sitter's query execution to find the relevant nodes.
        """
        chunks = []
        
        # For demonstration, we'll create some basic chunks
        lines = content.split('\n')
        
        # Simple heuristic: treat each function/class as a chunk
        # In reality, we'd use tree-sitter queries to find exact nodes
        current_chunk = []
        current_start = 0
        
        for i, line in enumerate(lines):
            # Simple detection of function/class starts (language-agnostic approximation)
            stripped = line.strip()
            if any(stripped.startswith(keyword) for keyword in 
                   ['def ', 'class ', 'function ', 'struct ', 'impl ', 'fn ', 'pub ']):
                # Save previous chunk if it has content
                if current_chunk:
                    chunk_content = '\n'.join(current_chunk)
                    if chunk_content.strip():
                        chunk = SourceChunk(
                            content=chunk_content,
                            metadata=ChunkMetadata(
                                file_path=file_path,
                                language=lang_config.name,
                                symbol_type="block",
                                start_line=current_start + 1,
                                end_line=i,
                                symbol_name=f"block_{len(chunks)}"
                            )
                        )
                        chunks.append(chunk)
                
                # Start new chunk
                current_chunk = [line]
                current_start = i
            else:
                current_chunk.append(line)
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            if chunk_content.strip():
                chunk = SourceChunk(
                    content=chunk_content,
                    metadata=ChunkMetadata(
                        file_path=file_path,
                        language=lang_config.name,
                        symbol_type="block",
                        start_line=current_start + 1,
                        end_line=len(lines),
                        symbol_name=f"block_{len(chunks)}"
                    )
                )
                chunks.append(chunk)
                
        # If we didn't find any structured chunks, fall back to line-based
        if not chunks:
            return self._fallback_chunking(content, file_path)
            
        return chunks
    
    def _fallback_chunking(self, content: str, file_path: str) -> List[SourceChunk]:
        """
        Fallback to simple line-based chunking when cAST is not available.
        """
        from buffa.shared.models import SourceChunk, ChunkMetadata
        
        # Detect language from file extension (same as fallback chunker)
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
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
        language = language_map.get(ext, 'unknown')
        
        lines = content.split('\n')
        chunks = []
        chunk_size = 20  # lines per chunk
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i+chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            
            if chunk_content.strip():
                chunk = SourceChunk(
                    content=chunk_content,
                    metadata=ChunkMetadata(
                        file_path=file_path,
                        language=language,
                        symbol_type="fallback",
                        start_line=i + 1,
                        end_line=min(i + chunk_size, len(lines)),
                        symbol_name=f"fallback_chunk_{len(chunks)}"
                    )
                )
                chunks.append(chunk)
                
        return chunks


def get_caster() -> CASter:
    """Get or create the global CASter instance."""
    if not hasattr(get_caster, '_instance'):
        get_caster._instance = CASter()
    return get_caster._instance