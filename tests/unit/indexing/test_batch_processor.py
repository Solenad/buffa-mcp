"""Tests for batch processor retry and backoff behavior."""

from __future__ import annotations

from typing import Any, List, Tuple

from buffa.indexing.batch_processor import BatchProcessor
from buffa.nim.client import NIMError, NIMErrorCategory


def test_process_batch_with_retries_uses_exponential_backoff(monkeypatch) -> None:
    """Retry delays follow 1s, 2s, 4s pattern for retryable failures."""
    processor = BatchProcessor(max_retries=3, retry_delay=1.0)
    sleep_calls: List[float] = []
    attempts = {"count": 0}

    monkeypatch.setattr("buffa.indexing.batch_processor.time.sleep", lambda delay: sleep_calls.append(delay))

    def failing_processor(_batch: List[Any]) -> Tuple[bool, List[Any]]:
        attempts["count"] += 1
        raise NIMError(
            message="temporary failure",
            category=NIMErrorCategory.TIMEOUT,
            retryable=True,
        )

    result = processor._process_batch_with_retries(["a", "b"], failing_processor, 1, 1)

    assert result.success is False
    assert attempts["count"] == 4
    assert sleep_calls == [1.0, 2.0, 4.0]


def test_process_batch_with_retries_succeeds_after_retry(monkeypatch) -> None:
    """Processor should eventually succeed and include returned results."""
    processor = BatchProcessor(max_retries=2, retry_delay=1.0)
    sleep_calls: List[float] = []
    attempts = {"count": 0}

    monkeypatch.setattr("buffa.indexing.batch_processor.time.sleep", lambda delay: sleep_calls.append(delay))

    def flaky_processor(batch: List[Any]) -> Tuple[bool, List[Any]]:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise NIMError(
                message="retry once",
                category=NIMErrorCategory.TRANSPORT,
                retryable=True,
            )
        return True, [str(item).upper() for item in batch]

    result = processor._process_batch_with_retries(["x"], flaky_processor, 1, 1)

    assert result.success is True
    assert result.results == ["X"]
    assert sleep_calls == [1.0]
