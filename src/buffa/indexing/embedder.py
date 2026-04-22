"""Batch passage embedding for chunk sets."""

from __future__ import annotations

import logging
from typing import List, Optional

from buffa.nim.embedding import EmbeddingClient
from buffa.nim.config import NimConfig
from buffa.shared.models import SourceChunk

logger = logging.getLogger(__name__)


class BatchEmbedder:
    """Handles batch embedding of source code chunks using NIM."""
    
    def __init__(self, config: NimConfig):
        self.embedding_client = EmbeddingClient(config)
        self.logger = logging.getLogger(__name__)
    
    def embed_chunks(self, chunks: List[SourceChunk], 
                    batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for a list of source code chunks in batches.
        
        Uses input_type="passage" as required for indexing code chunks.
        
        Args:
            chunks: List of SourceChunk objects to embed
            batch_size: Number of chunks to process per batch
            
        Returns:
            List of embedding vectors (same order as input chunks)
            
        Raises:
            NIMError: If embedding fails
        """
        if not chunks:
            return []
            
        all_embeddings = []
        
        # Process chunks in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = [chunk.content for chunk in batch]
            
            self.logger.debug(f"Embedding batch {i//batch_size + 1} "
                            f"({len(batch)} chunks)")
            
            try:
                # Use passage embedding for indexing (critical for quality)
                batch_embeddings = self.embedding_client.embed(
                    text=batch_texts,
                    input_type="passage"  # CRITICAL: Must use passage for indexing
                )
                all_embeddings.extend(batch_embeddings)
                
                self.logger.debug(f"Successfully embedded batch {i//batch_size + 1}")
                
            except Exception as e:
                self.logger.error(f"Failed to embed batch {i//batch_size + 1}: {e}")
                raise
        
        return all_embeddings
    
    def embed_chunk_contents(self, contents: List[str], 
                           batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for a list of text contents.
        
        Useful when we have raw text without chunk metadata.
        
        Args:
            contents: List of text strings to embed
            batch_size: Number of texts to process per batch
            
        Returns:
            List of embedding vectors (same order as input contents)
        """
        if not contents:
            return []
            
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(contents), batch_size):
            batch = contents[i:i + batch_size]
            
            self.logger.debug(f"Embedding content batch {i//batch_size + 1} "
                            f"({len(batch)} items)")
            
            try:
                batch_embeddings = self.embedding_client.embed(
                    text=batch,
                    input_type="passage"
                )
                all_embeddings.extend(batch_embeddings)
                
                self.logger.debug(f"Successfully embedded content batch {i//batch_size + 1}")
                
            except Exception as e:
                self.logger.error(f"Failed to embed content batch {i//batch_size + 1}: {e}")
                raise
        
        return all_embeddings


def create_batch_embedder(config: NimConfig) -> BatchEmbedder:
    """
    Factory function to create a BatchEmbedder instance.
    
    Args:
        config: NimConfig instance
        
    Returns:
        Configured BatchEmbedder instance
    """
    return BatchEmbedder(config)