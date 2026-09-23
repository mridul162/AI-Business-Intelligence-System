from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """Token pricing for one LLM model."""

    input_price_per_million: float
    output_price_per_million: float

    def calculate_cost(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        input_cost = (
            input_tokens / 1_000_000
        ) * self.input_price_per_million

        output_cost = (
            output_tokens / 1_000_000
        ) * self.output_price_per_million

        return input_cost + output_cost