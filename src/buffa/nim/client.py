"""Base NIM client with structured error handling."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx
from buffa.nim.config import NimConfig
from buffa.shared.errors import BuffaError


class NIMErrorCategory(Enum):
    """Structured error categories for NIM failures."""

    TRANSPORT = "transport"
    AUTH = "auth"
    TIMEOUT = "timeout"
    RESPONSE_SHAPE = "response_shape"


@dataclass(frozen=True)
class NIMError(BuffaError):
    """Structured NIM error with category and retry information."""
    
    message: str
    category: NIMErrorCategory
    retryable: bool
    endpoint: str | None = None
    request_id: str | None = None

    def __init__(self, message: str, category: NIMErrorCategory, retryable: bool, 
                 endpoint: str | None = None, request_id: str | None = None) -> None:
        super().__init__(message)
        object.__setattr__(self, 'message', message)
        object.__setattr__(self, 'category', category)
        object.__setattr__(self, 'retryable', retryable)
        object.__setattr__(self, 'endpoint', endpoint)
        object.__setattr__(self, 'request_id', request_id)

    def __str__(self) -> str:
        base = f"NIM {self.category.value} error"
        if self.endpoint:
            base += f" (endpoint: {self.endpoint})"
        if self.request_id:
            base += f" (request_id: {self.request_id})"
        if self.retryable:
            base += " [retryable]"
        return base + f": {super().__str__()}"


class BaseNIMClient:
    """Base client for NIM endpoint interactions."""

    def __init__(self, config: NimConfig, endpoint: str) -> None:
        self.config = config
        self.endpoint = endpoint.rstrip("/")
        self.client = httpx.Client(timeout=config.timeout_seconds)

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle HTTP response and map to structured errors.
        
        Args:
            response: HTTP response from NIM endpoint
            
        Returns:
            Parsed JSON response
            
        Raises:
            NIMError: For various failure categories
        """
        # Handle HTTP status codes
        if response.status_code == 401 or response.status_code == 403:
            raise NIMError(
                message="Authentication failed with NIM endpoint",
                category=NIMErrorCategory.AUTH,
                retryable=False,
                endpoint=self.endpoint,
                request_id=response.headers.get("x-nvidia-request-id"),
            )
        elif response.status_code == 408 or response.status_code == 429:
            raise NIMError(
                message=f"NIM endpoint returned status {response.status_code}",
                category=NIMErrorCategory.TIMEOUT,
                retryable=True,
                endpoint=self.endpoint,
                request_id=response.headers.get("x-nvidia-request-id"),
            )
        elif response.status_code >= 500:
            raise NIMError(
                message=f"NIM endpoint server error: {response.status_code}",
                category=NIMErrorCategory.TRANSPORT,
                retryable=True,
                endpoint=self.endpoint,
                request_id=response.headers.get("x-nvidia-request-id"),
            )
        elif not response.is_success:
            raise NIMError(
                message=f"NIM endpoint returned status {response.status_code}",
                category=NIMErrorCategory.TRANSPORT,
                retryable=False,
                endpoint=self.endpoint,
                request_id=response.headers.get("x-nvidia-request-id"),
            )

        # Parse JSON response
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise NIMError(
                message=f"Failed to parse NIM response as JSON: {exc}",
                category=NIMErrorCategory.RESPONSE_SHAPE,
                retryable=False,
                endpoint=self.endpoint,
                request_id=response.headers.get("x-nvidia-request-id"),
            ) from exc

        return data

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make HTTP request to NIM endpoint with error handling.
        
        Args:
            method: HTTP method
            path: Endpoint path
            **kwargs: Additional arguments for httpx
            
        Returns:
            Parsed JSON response
        """
        url = f"{self.endpoint}{path}"
        try:
            response = self.client.request(method, url, **kwargs)
            return self._handle_response(response)
        except httpx.TimeoutException as exc:
            raise NIMError(
                message=f"Request to NIM endpoint timed out: {exc}",
                category=NIMErrorCategory.TIMEOUT,
                retryable=True,
                endpoint=self.endpoint,
            ) from exc
        except httpx.NetworkError as exc:
            raise NIMError(
                message=f"Network error contacting NIM endpoint: {exc}",
                category=NIMErrorCategory.TRANSPORT,
                retryable=True,
                endpoint=self.endpoint,
            ) from exc

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    def __enter__(self) -> "BaseNIMClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()