import re
from typing import TypedDict
from anthropic.types import ModelParam


class Pricing(TypedDict):
    input: float
    output: float


PRICING_PER_MILLION: dict[ModelParam, Pricing] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

# API responses report the resolved snapshot id, e.g. "claude-haiku-4-5-20251001",
# but pricing is keyed by the alias. Strip a trailing "-YYYYMMDD" date suffix.
_DATE_SUFFIX = re.compile(r"-\d{8}$")


def pricing_for(model: str) -> Pricing | None:
    return PRICING_PER_MILLION.get(model) or PRICING_PER_MILLION.get(
        _DATE_SUFFIX.sub("", model)
    )
