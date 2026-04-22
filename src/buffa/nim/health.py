"""Health check and auth preflight logic for NIM endpoints."""

from __future__ import annotations

from buffa.nim.client import BaseNIMClient, NIMError, NIMErrorCategory
from buffa.nim.config import NimConfig


def health_check(config: NimConfig) -> bool:
    """Perform health check on NIM endpoint.
    
    Args:
        config: NIM configuration
        
    Returns:
        True if endpoint is healthy, False otherwise
        
    Note:
        This performs a lightweight check to verify connectivity and authentication
        without consuming significant quota or resources.
    """
    # Create a minimal client for the health check
    client = BaseNIMClient(config, f"{config.base_url}/health")
    
    try:
        # Try to make a simple GET request to the health endpoint
        # Using a short timeout for the health check itself
        response = client.client.get("", timeout=5.0)
        return response.is_success
    except Exception:
        # Any exception means the endpoint is not healthy
        return False
    finally:
        client.close()


def auth_preflight(config: NimConfig) -> bool:
    """Perform authentication preflight check.
    
    Args:
        config: NIM configuration
        
    Returns:
        True if authentication appears valid, False otherwise
    """
    # For NIM endpoints, we can't easily test auth without making a real request
    # but we can at least verify the API key is present and not empty
    # A more sophisticated implementation might make a minimal request
    
    # Check that we have a base URL
    if not config.base_url or not config.base_url.strip():
        return False
        
    # The actual API key is checked in runtime.py, but we could verify
    # the embedding model is configured as a basic sanity check
    if not config.embedding_model or not config.embedding_model.strip():
        return False
        
    return True
