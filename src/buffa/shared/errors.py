"""Shared error types for Buffa."""

from __future__ import annotations


class BuffaError(Exception):
    """Base error type for Buffa runtime failures."""


class StartupDiagnosticError(BuffaError):
    """Raised when startup environment diagnostics fail."""
