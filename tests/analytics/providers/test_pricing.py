from etl.analytics.providers.pricing import ModelPricing


def test_calculate_combined_cost() -> None:
    pricing = ModelPricing(
        input_price_per_million=1.0,
        output_price_per_million=2.0,
    )

    cost = pricing.calculate_cost(
        input_tokens=1_000_000,
        output_tokens=500_000,
    )

    assert cost == 2.0