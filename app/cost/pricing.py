from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    output_per_million: Decimal


class PricingTable:
    def __init__(self, models: dict[str, ModelPrice]) -> None:
        self.models = models

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PricingTable":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        models: dict[str, ModelPrice] = {}
        for model, value in (data.get("models") or {}).items():
            models[model] = ModelPrice(
                input_per_million=Decimal(str(value["input_per_million"])),
                output_per_million=Decimal(str(value["output_per_million"])),
            )
        return cls(models)

    def get(self, model: str | None) -> ModelPrice | None:
        if model is None:
            return None
        return self.models.get(model)

