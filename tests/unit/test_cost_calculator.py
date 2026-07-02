from decimal import Decimal

from app.cost.calculator import CostCalculator
from app.cost.pricing import ModelPrice, PricingTable


def test_calculate_known_model_cost() -> None:
    calculator = CostCalculator(
        PricingTable({"gpt-test": ModelPrice(input_per_million=Decimal("2.50"), output_per_million=Decimal("10.00"))})
    )

    assert calculator.calculate(model="gpt-test", prompt_tokens=1000, completion_tokens=2000) == Decimal("0.022500")


def test_unknown_model_returns_none() -> None:
    calculator = CostCalculator(PricingTable({}))

    assert calculator.calculate(model="missing", prompt_tokens=1000, completion_tokens=2000) is None

