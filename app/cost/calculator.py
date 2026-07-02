from __future__ import annotations

import logging
from decimal import Decimal

from app.cost.pricing import PricingTable

logger = logging.getLogger(__name__)


class CostCalculator:
    def __init__(self, pricing_table: PricingTable) -> None:
        self.pricing_table = pricing_table

    def calculate(
        self,
        *,
        model: str | None,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> Decimal | None:
        if prompt_tokens is None or completion_tokens is None:
            return None

        price = self.pricing_table.get(model)
        if price is None:
            logger.warning("No pricing entry found for model %s; cost_usd will be null", model)
            return None

        input_cost = Decimal(prompt_tokens) * price.input_per_million / Decimal(1_000_000)
        output_cost = Decimal(completion_tokens) * price.output_per_million / Decimal(1_000_000)
        return (input_cost + output_cost).quantize(Decimal("0.000001"))

