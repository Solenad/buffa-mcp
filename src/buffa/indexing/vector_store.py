"""Vector upsert contract with stable chunk IDs and metadata persistence."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from buffa.shared.models import SourceChunk, ChunkMetadata

logger = logging.getLogger(__name__)


@dataclass
class VectorRecord:
    """Record to be upserted into vector database."""
    id: str
    vector: List[float]
    payload: Dict[str, Any]


class VectorStore:
    """Abstract vector store interface for Buffa indexing."""
    
    def __init__(self, collection_name: str = "buffa_chunks"):
        self.collection_name = collection_name
        self.logger = logging.getLogger(__name__)
        # In a real implementation, we would initialize the actual vector DB client here
    
    def upsert_chunks(self, chunks: List[SourceChunk], 
                     embeddings: List[List[float]]) -> bool:
        """
        Upsert chunks with their embeddings into the vector store.
        
        Args:
            chunks: List of SourceChunk objects
            embeddings: List of embedding vectors (same order as chunks)
            
        Returns:
            True if successful, False otherwise
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
            
        if not chunks:
            return True
            
        try:
            # Generate vector records with stable IDs and rich payloads
            records = self._create_vector_records(chunks, embeddings)
            
            # In a real implementation, we would:
            # 1. Ensure collection exists
            # 2. Upsert the records to the vector database
            # For now, we'll log what we would do
            
            self.logger.info(f"Would upsert {len(records)} records to {self.collection_name}")
            
            # Simulate successful upsert
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to upsert chunks: {e}")
            return False
    
    def _create_vector_records(self, chunks: List[SourceChunk], 
                              embeddings: List[List[float]]) -> List[VectorRecord]:
        """
        Create vector records with stable IDs and metadata persistence.
        
        Args:
            chunks: List of SourceChunk objects
            embeddings: List of embedding vectors
            
        Returns:
            List of VectorRecord objects ready for upsert
        """
        records = []
        
        for chunk, embedding in zip(chunks, embeddings):
            # Generate stable ID based on file path, content hash, and chunk position
            stable_id = self._generate_stable_id(chunk)
            
            # Create rich payload with all metadata
            payload = {
                "file_path": chunk.metadata.file_path,
                "language": chunk.metadata.language,
                "symbol_type": chunk.metadata.symbol_type,
                "symbol_name": chunk.metadata.symbol_name,
                "start_line": chunk.metadata.start_line,
                "end_line": chunk.metadata.end_line,
                "content": chunk.content,
                "chunk_hash": self._compute_content_hash(chunk.content),
                "raw_token_estimate": chunk.metadata.raw_token_estimate,
                "compressed_token_estimate": chunk.metadata.compressed_token_estimate
            }
            
            # Add optional hash if available
            if chunk.metadata.hash:
                payload["content_hash"] = chunk.metadata.hash
            
            record = VectorRecord(
                id=stable_id,
                vector=embedding,
                payload=payload
            )
            records.append(record)
        
        return records
    
    def _generate_stable_id(self, chunk: SourceChunk) -> str:
        """
        Generate a stable, deterministic ID for a chunk.
        
        The ID should be based on immutable properties so that
        the same chunk gets the same ID across reindexing operations.
        
        Args:
            chunk: SourceChunk to generate ID for
            
        Returns:
            Stable string ID
        """
        # Create a string that uniquely identifies this chunk
        id_components = [
            chunk.metadata.file_path,
            str(chunk.metadata.start_line),
            str(chunk.metadata.end_line),
            chunk.metadata.symbol_name or "",
            chunk.metadata.symbol_type
        ]
        
        # Add content hash if available, otherwise hash the content
        if chunk.metadata.hash:
            id_components.append(chunk.metadata.hash)
        else:
            content_hash = self._compute_content_hash(chunk.content)
            id_components.append(content_hash)
        
        # Join and hash to create fixed-length ID
        id_string = "|".join(id_components)
        hash_object = hashlib.sha256(id_string.encode())
        hex_dig = hash_object.hexdigest()
        
        # Return first 16 chars for reasonable length
        return hex_dig[:16]
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def delete_by_file_path(self, file_path: str) -> bool:
        """
        Delete all vectors associated with a file path.
        
        Used during incremental reindexing when files are modified or deleted.
        
        Args:
            file_path: Path to file whose vectors should be deleted
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # In a real implementation, we would:
            # 1. Query for all points with matching file_path in payload
            # 2. Delete those points
            self.logger.info(f"Would delete vectors for file: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete vectors for {file_path}: {e}")
            return False
    
    def delete_by_old_path(self, old_file_path: str, new_file_path: str) -> bool:
        """
        Handle file rename by deleting vectors for the old path.
        
        During incremental reindexing, when a file is renamed, we need to
        remove the old vectors and allow the new file to be indexed.
        
        Args:
            old_file_path: Original file path before rename
            new_file_path: New file path after rename
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # In a real implementation, we would:
            # 1. Query for all points with matching old_file_path in payload
            # 2. Delete those points (since the file has moved)
            # 3. The new file will be indexed normally during the reindex pass
            self.logger.info(f"Would handle rename: {old_file_path} -> {new_file_path}")
            self.logger.info(f"Would delete vectors for old path: {old_file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to handle file rename from {old_file_path} to {new_file_path}: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about the vector collection.
        
        Returns:
            Dictionary with collection statistics and info
        """
        try:
            # In a real implementation, we would query the vector DB
            # For now, return placeholder info
            return {
                "collection_name": self.collection_name,
                "points_count": 0,  # Would be actual count
                "status": "green"   # Would be actual status
            }
        except Exception as e:
            self.logger.error(f"Failed to get collection info: {e}")
            return {"error": str(e)}


def create_vector_store(collection_name: str = "buffa_chunks") -> VectorStore:
    """
    Factory function to create a VectorStore instance.
    
    Args:
        collection_name: Name of the vector collection
        
    Returns:
        Configured VectorStore instance
    """
    return VectorStore(collection_name=collection_name)