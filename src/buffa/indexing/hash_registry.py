"""File hash registry for skip/reindex decisions."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Dict, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """Record of a file's state for incremental indexing."""
    path: str
    size: int
    mtime: float
    content_hash: str
    last_indexed: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileRecord':
        """Create from dictionary."""
        return cls(**data)


class FileHashRegistry:
    """Registry for tracking file hashes to enable incremental reindexing."""
    
    def __init__(self, registry_path: str = ".buffa/file_hashes.json"):
        """
        Initialize file hash registry.
        
        Args:
            registry_path: Path to the registry file
        """
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry: Dict[str, FileRecord] = {}
        self._load_registry()
        logger.info(f"Initialized file hash registry at {self.registry_path}")
    
    def _load_registry(self) -> None:
        """Load registry from disk."""
        if not self.registry_path.exists():
            logger.debug(f"No existing registry found at {self.registry_path}")
            return
            
        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                self._registry = {
                    path: FileRecord.from_dict(record)
                    for path, record in data.items()
                }
            logger.info(f"Loaded {len(self._registry)} file records from registry")
        except Exception as e:
            logger.warning(f"Failed to load registry from {self.registry_path}: {e}")
            self._registry = {}
    
    def _save_registry(self) -> None:
        """Save registry to disk."""
        try:
            # Convert to serializable format
            data = {
                path: record.to_dict()
                for path, record in self._registry.items()
            }
            
            # Write to temporary file first for atomicity
            temp_path = self.registry_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            temp_path.replace(self.registry_path)
            logger.debug(f"Saved registry with {len(self._registry)} records")
        except Exception as e:
            logger.error(f"Failed to save registry to {self.registry_path}: {e}")
    
    def _compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA256 hash of file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal SHA256 hash
        """
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
        except IOError as e:
            logger.error(f"Failed to read file {file_path} for hashing: {e}")
            raise
        return hash_sha256.hexdigest()
    
    def _get_file_stats(self, file_path: str) -> Optional[tuple[int, float]]:
        """
        Get file size and modification time.
        
        Args:
            file_path: Path to file
            
        Returns:
            Tuple of (size, mtime) or None if file doesn't exist
        """
        try:
            stat = os.stat(file_path)
            return stat.st_size, stat.st_mtime
        except OSError as e:
            logger.debug(f"Could not stat file {file_path}: {e}")
            return None
    
    def should_reindex(self, file_path: str) -> bool:
        """
        Determine if a file needs to be reindexed.
        
        Args:
            file_path: Path to file to check
            
        Returns:
            True if file should be indexed/reindexed, False if can be skipped
        """
        # Get current file stats
        stats = self._get_file_stats(file_path)
        if stats is None:
            # File doesn't exist or can't be accessed
            # If we have a record, it means the file was deleted
            if file_path in self._registry:
                logger.debug(f"File {file_path} no longer exists, removing from registry")
                del self._registry[file_path]
                self._save_registry()
            return False
            
        current_size, current_mtime = stats
        
        # Check if we have a previous record
        if file_path not in self._registry:
            logger.debug(f"No previous record for {file_path}, will index")
            return True
            
        record = self._registry[file_path]
        
        # Check if file has changed
        if record.size != current_size or record.mtime != current_mtime:
            logger.debug(f"File {file_path} has changed (size: {record.size}->{current_size}, "
                        f"mtime: {record.mtime}->{current_mtime}), will reindex")
            return True
        
        # File appears unchanged, verify with content hash as safety check
        try:
            current_hash = self._compute_file_hash(file_path)
            if record.content_hash != current_hash:
                logger.debug(f"File {file_path} content hash changed, will reindex")
                return True
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            # If we can't compute hash, assume it changed to be safe
            return True
        
        logger.debug(f"File {file_path} unchanged, skipping")
        return False
    
    def record_indexed(self, file_path: str) -> None:
        """
        Record that a file has been indexed.
        
        Args:
            file_path: Path to file that was indexed
        """
        stats = self._get_file_stats(file_path)
        if stats is None:
            logger.warning(f"Could not stat file {file_path} when recording indexing")
            return
            
        size, mtime = stats
        
        try:
            content_hash = self._compute_file_hash(file_path)
        except Exception as e:
            logger.error(f"Failed to compute hash for {file_path}: {e}")
            return
        
        record = FileRecord(
            path=file_path,
            size=size,
            mtime=mtime,
            content_hash=content_hash,
            last_indexed=time.time()
        )
        
        self._registry[file_path] = record
        logger.debug(f"Recorded indexing for {file_path}")
    
    def remove_file(self, file_path: str) -> None:
        """
        Remove a file from the registry (when file is deleted).
        
        Args:
            file_path: Path to file to remove
        """
        if file_path in self._registry:
            del self._registry[file_path]
            logger.debug(f"Removed {file_path} from registry")
    
    def get_indexed_files(self) -> Set[str]:
        """
        Get set of all indexed file paths.
        
        Returns:
            Set of file paths that have been indexed
        """
        return set(self._registry.keys())
    
    def get_file_record(self, file_path: str) -> Optional[FileRecord]:
        """
        Get the record for a specific file.
        
        Args:
            file_path: Path to file
            
        Returns:
            FileRecord if found, None otherwise
        """
        return self._registry.get(file_path)
    
    def save(self) -> None:
        """Save the registry to disk."""
        self._save_registry()
    
    def clear(self) -> None:
        """Clear all records from the registry."""
        self._registry.clear()
        self._save_registry()
        logger.info("Cleared file hash registry")


# Global registry instance
_registry: Optional[FileHashRegistry] = None


def get_file_hash_registry(registry_path: str = ".buffa/file_hashes.json") -> FileHashRegistry:
    """
    Get or create the global file hash registry instance.
    
    Args:
        registry_path: Path to the registry file
        
    Returns:
        FileHashRegistry instance
    """
    global _registry
    if _registry is None or _registry.registry_path != Path(registry_path):
        _registry = FileHashRegistry(registry_path)
    return _registry


def should_reindex_file(file_path: str, 
                       registry_path: str = ".buffa/file_hashes.json") -> bool:
    """
    Convenience function to check if a file should be reindexed.
    
    Args:
        file_path: Path to file to check
        registry_path: Path to registry file
        
    Returns:
        True if file should be indexed/reindexed
    """
    registry = get_file_hash_registry(registry_path)
    return registry.should_reindex(file_path)


def record_file_indexed(file_path: str,
                       registry_path: str = ".buffa/file_hashes.json") -> None:
    """
    Convenience function to record that a file has been indexed.
    
    Args:
        file_path: Path to file that was indexed
        registry_path: Path to registry file
    """
    registry = get_file_hash_registry(registry_path)
    registry.record_indexed(file_path)