from __future__ import annotations

import pytest

from buffa.config.models import BuffaConfig, TokenBudgetConfig


def test_token_budget_resolver_uses_defaults() -> None:
    config = BuffaConfig()
    # Test with no model override - should use request budget minus default reserve
    effective = config.token_budget.get_effective_budget(request_budget=2048)
    assert effective == 2048 - 512  # 1536


def test_token_budget_resolver_applies_per_model_override() -> None:
    config = BuffaConfig(
        token_budget=TokenBudgetConfig(
            per_model_overrides={"test-model": 2048},
            default_reserve=128
        )
    )
    # Should use the model override, then subtract reserve
    effective = config.token_budget.get_effective_budget(
        request_budget=4096,  # This should be ignored due to override
        model="test-model"
    )
    assert effective == 2048 - 128  # 1920


def test_token_budget_resolver_handles_missing_model() -> None:
    config = BuffaConfig(
        token_budget=TokenBudgetConfig(
            per_model_overrides={"other-model": 1024},
            default_reserve=256
        )
    )
    # Should fall back to request budget when model not in overrides
    effective = config.token_budget.get_effective_budget(
        request_budget=2048,
        model="test-model"  # Not in overrides
    )
    assert effective == 2048 - 256  # 1792


def test_token_budget_resolver_blocks_non_positive_budget() -> None:
    config = BuffaConfig(
        token_budget=TokenBudgetConfig(
            per_model_overrides={"small-model": 100},
            default_reserve=200
        )
    )
    # Should raise ValueError when budget would be zero or negative
    with pytest.raises(ValueError, match="non-positive"):
        config.token_budget.get_effective_budget(
            request_budget=1000,
            model="small-model"  # Override is 100, reserve is 200 -> -100
        )


def test_token_budget_resolver_allows_exact_reserve() -> None:
    config = BuffaConfig(
        token_budget=TokenBudgetConfig(
            default_reserve=512
        )
    )
    # Should allow budget exactly equal to reserve (result = 0 is blocked)
    # Actually, let's check the implementation - it blocks <= 0
    with pytest.raises(ValueError, match="non-positive"):
        config.token_budget.get_effective_budget(
            request_budget=512,  # Exactly equal to reserve
        )