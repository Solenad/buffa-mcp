"""Configuration models for Buffa."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TokenBudgetConfig(BaseModel):
    """Configuration for token budget and reserves."""

    per_model_overrides: dict[str, int] = Field(
        default_factory=dict,
        description="Model-specific token budget overrides.",
    )
    default_reserve: int = Field(
        default=512,
        description="Default token reserve to subtract from available budget.",
    )

    def get_effective_budget(
        self, request_budget: int, model: str | None = None
    ) -> int:
        """Calculate the effective token budget for a request.

        Applies model-specific overrides if present,
        then subtracts the reserve.

        Args:
            request_budget: The requested token budget
            model: Optional model name to look up in per_model_overrides

        Returns:
            Effective budget after applying overrides and subtracting reserve

        Raises:
            ValueError: If the effective budget would be zero or negative
        """
        # Use model-specific override if provided, otherwise use request budget
        effective_budget = request_budget
        if model and model in self.per_model_overrides:
            effective_budget = self.per_model_overrides[model]

        # Subtract the reserve
        available_budget = effective_budget - self.default_reserve

        if available_budget <= 0:
            raise ValueError(
                f"Available token budget is non-positive: {available_budget} "
                f"(request: {request_budget}, model override: {model}, "
                f"reserve: {self.default_reserve})"
            )

        return available_budget


class NimConfig(BaseModel):
    """Configuration for NIM endpoint connectivity."""

    embedding_model: str = Field(
        default="nvidia/nv-embedqa-e5-v5",
        description="NIM model to use for embeddings.",
    )
    reranking_model: str = Field(
        default="nvidia/nv-rerankqa-mistral-4b-v3",
        description="NIM model to use for reranking.",
    )
    timeout_seconds: int = Field(
        default=30,
        description="Timeout for NIM endpoint requests.",
    )


class BuffaConfig(BaseModel):
    """Root configuration contract for .buffa.json."""

    token_budget: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    nim: NimConfig = Field(default_factory=NimConfig)
