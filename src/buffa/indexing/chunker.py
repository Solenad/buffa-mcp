"""cAST-based chunking adapters for Buffa indexing engine."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    import tree_sitter
    TREE_SITTER_AVAILABLE = True
except ImportError:
    tree_sitter = None
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
    query: Any = None


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
                parser, query = self._build_parser_and_query(config["name"], config["query"])
                lang_config = LanguageConfig(
                    name=config["name"],
                    extensions=config["extensions"],
                    parser=parser,
                    query_string=config["query"],
                    query=query,
                )
                for ext in config["extensions"]:
                    self.languages[ext] = lang_config
                    
                if parser is not None and query is not None:
                    logger.info(f"Initialized cAST parser for {config['name']}")
                else:
                    logger.debug(f"Initialized language config for {config['name']} (parser unavailable)")
            except Exception as e:
                logger.error(f"Failed to initialize parser for {config['name']}: {e}")

    def _build_parser_and_query(self, language_name: str, query_string: str) -> Tuple[Optional[Any], Optional[Any]]:
        """Build parser/query pair for a language when tree-sitter is available."""
        if not TREE_SITTER_AVAILABLE:
            return None, None

        language = self._resolve_language(language_name)
        if language is None:
            return None, None

        try:
            parser = tree_sitter.Parser()
            if hasattr(parser, "set_language"):
                parser.set_language(language)
            else:  # Newer tree-sitter Python bindings expose .language property.
                parser.language = language
        except Exception:
            return None, None

        query = self._compile_query(language, query_string)
        if query is None:
            return None, None

        return parser, query

    def _resolve_language(self, language_name: str) -> Optional[Any]:
        """Resolve a tree-sitter language object by name."""
        if not TREE_SITTER_AVAILABLE:
            return None

        try:
            from tree_sitter_languages import get_language  # type: ignore

            return get_language(language_name)
        except Exception:
            pass

        module_candidates: Dict[str, Tuple[str, List[str]]] = {
            "python": ("tree_sitter_python", ["language"]),
            "javascript": ("tree_sitter_javascript", ["language", "language_javascript"]),
            "typescript": ("tree_sitter_typescript", ["language_typescript", "language", "typescript"]),
            "go": ("tree_sitter_go", ["language"]),
            "rust": ("tree_sitter_rust", ["language"]),
            "java": ("tree_sitter_java", ["language"]),
            "cpp": ("tree_sitter_cpp", ["language"]),
        }

        module_info = module_candidates.get(language_name)
        if module_info is None:
            return None

        module_name, attribute_candidates = module_info
        try:
            module = __import__(module_name, fromlist=["*"])
        except Exception:
            return None

        for attribute_name in attribute_candidates:
            attribute = getattr(module, attribute_name, None)
            if attribute is None:
                continue

            if callable(attribute):
                try:
                    return attribute()
                except Exception:
                    continue
            return attribute

        return None

    def _compile_query(self, language: Any, query_string: str) -> Optional[Any]:
        """Compile query with compatibility across tree-sitter Python versions."""
        try:
            if hasattr(language, "query"):
                return language.query(query_string)
            return tree_sitter.Query(language, query_string)
        except Exception:
            return None
    
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
        """
        if lang_config.parser is None or lang_config.query is None:
            return self._fallback_chunking(content, file_path)

        source_bytes = content.encode("utf-8", errors="ignore")
        tree = lang_config.parser.parse(source_bytes)

        captures = self._extract_captures(lang_config.query, tree)
        if not captures:
            return self._fallback_chunking(content, file_path)

        chunks: List[SourceChunk] = []
        seen: set[Tuple[int, int, str]] = set()

        for index, (node, capture_name) in enumerate(captures):
            start_byte = getattr(node, "start_byte", None)
            end_byte = getattr(node, "end_byte", None)
            if not isinstance(start_byte, int) or not isinstance(end_byte, int) or end_byte <= start_byte:
                continue

            symbol_type = self._normalize_capture_name(capture_name)
            dedupe_key = (start_byte, end_byte, symbol_type)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            chunk_content = source_bytes[start_byte:end_byte].decode("utf-8", errors="ignore")
            if not chunk_content.strip():
                continue

            start_point = getattr(node, "start_point", (0, 0))
            end_point = getattr(node, "end_point", start_point)
            start_line = int(start_point[0]) + 1
            end_line = int(end_point[0]) + 1

            chunk = SourceChunk(
                content=chunk_content,
                metadata=ChunkMetadata(
                    file_path=file_path,
                    language=lang_config.name,
                    symbol_type=symbol_type,
                    start_line=max(1, start_line),
                    end_line=max(start_line, end_line),
                    symbol_name=self._extract_symbol_name(chunk_content, symbol_type, index),
                ),
            )
            chunks.append(chunk)

        if not chunks:
            return self._fallback_chunking(content, file_path)

        chunks.sort(key=lambda chunk: (chunk.metadata.start_line, chunk.metadata.end_line))
        return chunks

    def _extract_captures(self, query: Any, tree: Any) -> List[Tuple[Any, str]]:
        """Extract captures from a tree-sitter query across API variants."""
        root_node = tree.root_node

        raw_captures: Any
        try:
            raw_captures = query.captures(root_node)
        except Exception:
            try:
                cursor = tree_sitter.QueryCursor()
                raw_captures = cursor.captures(query, root_node)
            except Exception:
                return []

        normalized: List[Tuple[Any, str]] = []

        if isinstance(raw_captures, dict):
            for name, nodes in raw_captures.items():
                for node in nodes:
                    normalized.append((node, str(name)))
            return self._sort_captures(normalized)

        if isinstance(raw_captures, tuple) and len(raw_captures) == 2 and isinstance(raw_captures[0], dict):
            captures_dict = raw_captures[0]
            for name, nodes in captures_dict.items():
                for node in nodes:
                    normalized.append((node, str(name)))
            return self._sort_captures(normalized)

        if isinstance(raw_captures, list):
            for capture in raw_captures:
                if not isinstance(capture, tuple) or len(capture) != 2:
                    continue
                node, capture_id_or_name = capture
                if isinstance(capture_id_or_name, str):
                    capture_name = capture_id_or_name
                elif isinstance(capture_id_or_name, int):
                    capture_name = self._capture_name_from_index(query, capture_id_or_name)
                else:
                    capture_name = str(capture_id_or_name)
                normalized.append((node, capture_name))
            return self._sort_captures(normalized)

        return []

    def _capture_name_from_index(self, query: Any, capture_index: int) -> str:
        """Resolve capture name from numeric index for API compatibility."""
        for resolver_name in ("capture_name", "capture_name_for_id"):
            resolver = getattr(query, resolver_name, None)
            if resolver is None:
                continue
            try:
                value = resolver(capture_index)
                if isinstance(value, str):
                    return value
            except Exception:
                continue
        return f"capture_{capture_index}"

    def _sort_captures(self, captures: List[Tuple[Any, str]]) -> List[Tuple[Any, str]]:
        """Sort captures by source position."""
        return sorted(captures, key=lambda item: (getattr(item[0], "start_byte", 0), getattr(item[0], "end_byte", 0)))

    def _normalize_capture_name(self, capture_name: str) -> str:
        """Normalize capture labels to symbol types."""
        normalized = capture_name.strip().lstrip("@").lower()
        return normalized or "block"

    def _extract_symbol_name(self, chunk_content: str, symbol_type: str, index: int) -> str:
        """Extract best-effort symbol name from chunk content."""
        pattern_groups = {
            "function": [r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)", r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)", r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)", r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)"],
            "method": [r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)", r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\("],
            "class": [r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)", r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)"],
            "interface": [r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)", r"\btrait\s+([A-Za-z_][A-Za-z0-9_]*)"],
            "impl": [r"\bimpl\s+([A-Za-z_][A-Za-z0-9_]*)"],
        }

        for pattern in pattern_groups.get(symbol_type, []):
            match = re.search(pattern, chunk_content)
            if match:
                return match.group(1)

        return f"{symbol_type}_{index}"
    
    def _fallback_chunking(self, content: str, file_path: str) -> List[SourceChunk]:
        """
        Fallback to simple line-based chunking when cAST is not available.
        """
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
