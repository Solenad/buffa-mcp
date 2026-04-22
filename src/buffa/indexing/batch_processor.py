"""Batch-level error handling and partial-progress reporting."""

from __future__ import annotations

import logging
import time
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field

from buffa.shared.models import SourceChunk
from buffa.nim.client import NIMError, NIMErrorCategory

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result of processing a batch."""
    success: bool
    processed_count: int
    failed_count: int
    results: List[Any] = field(default_factory=list)
    errors: List[NIMError] = field(default_factory=list)
    processing_time: float = 0.0
    

@dataclass
class ProgressReport:
    """Progress report for batch processing operations."""
    total_batches: int
    completed_batches: int
    total_items: int
    processed_items: int
    failed_items: int
    success_rate: float
    elapsed_time: float
    estimated_remaining: float
    current_batch: int = 0
    

class BatchProcessor:
    """Handles batch processing with error handling and progress reporting."""
    
    def __init__(self, 
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 progress_callback: Optional[Callable[[ProgressReport], None]] = None):
        """
        Initialize batch processor.
        
        Args:
            max_retries: Maximum number of retry attempts for failed batches
            retry_delay: Delay between retry attempts in seconds
            progress_callback: Optional callback for progress updates
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)
        self._start_time: Optional[float] = None
    
    def process_batches(self, 
                       items: List[Any],
                       batch_size: int,
                       processor_func: Callable[[List[Any]], Tuple[bool, List[Any]]],
                       description: str = "Processing") -> Tuple[List[Any], List[NIMError]]:
        """
        Process items in batches with error handling and progress reporting.
        
        Args:
            items: List of items to process
            batch_size: Number of items per batch
            processor_func: Function that processes a batch and returns (success, results)
            description: Description for progress reporting
            
        Returns:
            Tuple of (all_results, all_errors)
        """
        if not items:
            return [], []
            
        self._start_time = time.time()
        total_batches = (len(items) + batch_size - 1) // batch_size
        all_results: List[Any] = []
        all_errors: List[NIMError] = []
        
        self.logger.info(f"Starting {description}: {len(items)} items in {total_batches} batches")
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(items))
            batch = items[start_idx:end_idx]
            
            batch_num = batch_idx + 1
            self.logger.debug(f"Processing batch {batch_num}/{total_batches} "
                            f"({len(batch)} items)")
            
            # Process batch with retries
            batch_result = self._process_batch_with_retries(
                batch, processor_func, batch_num, total_batches
            )
            
            # Collect results and errors
            if batch_result.success:
                all_results.extend(batch_result.results)
            else:
                all_errors.extend(batch_result.errors)
            
            # Update progress
            self._report_progress(
                batch_idx + 1, total_batches, len(items), 
                len(all_results), len(all_errors), description
            )
            
            # If batch failed completely, we might want to stop or continue
            # For now, we continue processing other batches
        
        elapsed_time = time.time() - self._start_time if self._start_time else 0.0
        self.logger.info(f"Completed {description}: "
                        f"{len(all_results)} successful, {len(all_errors)} failed "
                        f"in {elapsed_time:.2f}s")
        
        return all_results, all_errors
    
    def _process_batch_with_retries(self, 
                                   batch: List[Any],
                                   processor_func: Callable[[List[Any]], Tuple[bool, List[Any]]],
                                   batch_num: int,
                                   total_batches: int) -> BatchResult:
        """
        Process a single batch with retry logic.
        
        Args:
            batch: Items to process in this batch
            processor_func: Function to process the batch
            batch_num: Current batch number
            total_batches: Total number of batches
            
        Returns:
            BatchResult with success/failure information
        """
        start_time = time.time()
        last_error: Optional[NIMError] = None
        
        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                success, results = processor_func(batch)
                
                if success:
                    processing_time = time.time() - start_time
                    return BatchResult(
                        success=True,
                        processed_count=len(batch),
                        failed_count=0,
                        results=results,
                        processing_time=processing_time
                    )
                else:
                    # Processor returned failure - treat as error
                    raise NIMError(
                        message=f"Batch processor returned failure for batch {batch_num}",
                        category=NIMErrorCategory.RESPONSE_SHAPE,
                        retryable=False
                    )
                    
            except NIMError as e:
                last_error = e
                if attempt < self.max_retries and e.retryable:
                    delay = min(self.retry_delay * (2 ** attempt), 8.0)
                    self.logger.warning(f"Batch {batch_num} attempt {attempt + 1} failed: {e}. "
                                      f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Batch {batch_num} failed after {attempt + 1} attempts: {e}")
                    break  # No more retries or not retryable
                    
            except Exception as e:
                # Convert unexpected errors to NIMError
                nim_error = NIMError(
                    message=f"Unexpected error processing batch {batch_num}: {str(e)}",
                    category=NIMErrorCategory.TRANSPORT,
                    retryable=True if attempt < self.max_retries else False
                )
                last_error = nim_error
                if attempt < self.max_retries and nim_error.retryable:
                    delay = min(self.retry_delay * (2 ** attempt), 8.0)
                    self.logger.warning(f"Batch {batch_num} attempt {attempt + 1} failed: {e}. "
                                      f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Batch {batch_num} failed after {attempt + 1} attempts: {e}")
                    break  # No more retries or not retryable
        
        # If we get here, all attempts failed
        processing_time = time.time() - start_time
        return BatchResult(
            success=False,
            processed_count=0,
            failed_count=len(batch),
            errors=[last_error] if last_error else [
                NIMError(
                    message=f"Batch {batch_num} failed after {self.max_retries + 1} attempts",
                    category=NIMErrorCategory.TRANSPORT,
                    retryable=False
                )
            ],
            processing_time=processing_time
        )
    
    def _report_progress(self, 
                        completed_batches: int,
                        total_batches: int,
                        total_items: int,
                        processed_items: int,
                        failed_items: int,
                        description: str) -> None:
        """
        Report progress through callback and logging.
        
        Args:
            completed_batches: Number of batches completed
            total_batches: Total number of batches
            total_items: Total number of items
            processed_items: Number of items successfully processed
            failed_items: Number of items failed
            description: Description for progress reporting
        """
        if self._start_time is None:
            elapsed_time = 0.0
            estimated_remaining = 0.0
        else:
            elapsed_time = time.time() - self._start_time
            if completed_batches > 0:
                time_per_batch = elapsed_time / completed_batches
                remaining_batches = total_batches - completed_batches
                estimated_remaining = time_per_batch * remaining_batches
            else:
                estimated_remaining = 0.0
        
        success_rate = (processed_items / max(processed_items + failed_items, 1)) * 100
        
        progress = ProgressReport(
            total_batches=total_batches,
            completed_batches=completed_batches,
            total_items=total_items,
            processed_items=processed_items,
            failed_items=failed_items,
            success_rate=success_rate,
            elapsed_time=elapsed_time,
            estimated_remaining=estimated_remaining,
            current_batch=completed_batches
        )
        
        # Log progress
        self.logger.info(
            f"{description} progress: {completed_batches}/{total_batches} batches, "
            f"{processed_items}/{total_items} items ({success_rate:.1f}% success)"
        )
        
        # Call progress callback if provided
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")


def process_chunks_in_batches(chunks: List[SourceChunk],
                            batch_size: int,
                            embedder_func: Callable[[List[str]], List[List[float]]],
                            description: str = "Embedding chunks") -> Tuple[List[List[float]], List[NIMError]]:
    """
    Convenience function to process chunks in batches for embedding.
    
    Args:
        chunks: List of SourceChunk objects to process
        batch_size: Number of chunks per batch
        embedder_func: Function that takes list of strings and returns embeddings
        description: Description for progress reporting
        
    Returns:
        Tuple of (all_embeddings, all_errors)
    """
    def batch_processor(batch: List[SourceChunk]) -> Tuple[bool, List[List[float]]]:
        """Process a batch of chunks for embedding."""
        try:
            texts = [chunk.content for chunk in batch]
            embeddings = embedder_func(texts)
            return True, embeddings
        except Exception as e:
            # Convert to NIMError if needed
            if isinstance(e, NIMError):
                raise
            else:
                raise NIMError(
                    message=f"Embedding failed: {str(e)}",
                    category=NIMErrorCategory.TRANSPORT,
                    retryable=True
                )
    
    processor = BatchProcessor()
    results, errors = processor.process_batches(
        chunks, batch_size, batch_processor, description
    )
    
    # Flatten results (each batch result is a list of embeddings)
    all_embeddings: List[List[float]] = []
    for batch_result in results:
        if isinstance(batch_result, list):
            all_embeddings.extend(batch_result)
    
    return all_embeddings, errors


def report_indexing_progress(stats: Dict[str, Any]) -> None:
    """
    Report indexing progress to stdout/logs.
    
    Args:
        stats: Dictionary containing indexing statistics
    """
    logger = logging.getLogger(__name__)
    
    files_processed = stats.get('files_processed', 0)
    files_total = stats.get('files_total', 0)
    chunks_created = stats.get('chunks_created', 0)
    chunks_indexed = stats.get('chunks_indexed', 0)
    errors = stats.get('errors', 0)
    
    logger.info(
        f"Indexing Progress: {files_processed}/{files_total} files, "
        f"{chunks_created} chunks created, {chunks_indexed} chunks indexed, "
        f"{errors} errors"
    )
