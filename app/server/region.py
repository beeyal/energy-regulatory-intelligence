"""
Region configuration loader for multi-market support.
Reads region.yaml and exposes typed RegionConfig objects.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class CarbonScheme(BaseModel):
    name: str
    operator: str
    threshold_kt: int
    price_unit: str
    price: float
    roadmap: str = ""
    shortfall_multiplier: float = 1.0
    baseline_decline_pct: float = 0.0


class Regulator(BaseModel):
    code: str
    name: str
    domain: str


class RegionConfig(BaseModel):
    code: str
    name: str
    flag: str
    currency: str
    market_name: str
    data_available: bool
    regulators: list[Regulator]
    carbon_scheme: CarbonScheme
    key_legislation: list[str]
    sub_regions: list[str]
    known_companies: list[str]
    system_prompt_context: str
    intent_extras: dict[str, list[str]] = {}

    @property
    def regulator_codes(self) -> list[str]:
        return [r.code for r in self.regulators]

    @property
    def regulator_summary(self) -> str:
        return ", ".join(f"{r.code} ({r.domain})" for r in self.regulators)


@lru_cache(maxsize=1)
def _load_yaml() -> dict[str, Any]:
    yaml_path = Path(__file__).parent.parent / "region.yaml"
    with open(yaml_path) as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=32)
def get_region(market_code: str) -> RegionConfig:
    """Return RegionConfig for a market code. Falls back to AU if unknown."""
    data = _load_yaml()
    markets = data.get("markets", {})
    code = market_code.upper() if market_code else "AU"
    if code not in markets:
        code = "AU"
    raw = markets[code]
    return RegionConfig(code=code, **raw)


def list_markets() -> list[dict[str, str]]:
    """Return summary list of all available markets for the region switcher."""
    data = _load_yaml()
    return [
        {
            "code": code,
            "name": info["name"],
            "flag": info["flag"],
            "market_name": info["market_name"],
            "data_available": str(info.get("data_available", False)).lower(),
        }
        for code, info in data.get("markets", {}).items()
    ]


def build_system_prompt(region: RegionConfig, context: str) -> str:
    """Build the full LLM system prompt for a given region and data context."""
    data_note = (
        ""
        if region.data_available
        else (
            f"\n\nNOTE: Live {region.name} data is not yet loaded in this deployment. "
            f"Answer based on your knowledge of {region.name} energy regulations, "
            f"using the {region.market_name} market context. "
            f"Be explicit when information is from general knowledge vs. loaded data."
        )
    )

    legislation = "\n".join(f"  - {leg}" for leg in region.key_legislation)
    regulators = "\n".join(
        f"  - {r.code}: {r.name} — {r.domain}" for r in region.regulators
    )

    return f"""{region.system_prompt_context}

REGULATORS:
{regulators}

KEY LEGISLATION:
{legislation}

CARBON SCHEME: {region.carbon_scheme.name}
  Operator: {region.carbon_scheme.operator}
  Price: {region.currency} {region.carbon_scheme.price}/{region.carbon_scheme.price_unit.split('/')[-1]}
{f'  Roadmap: {region.carbon_scheme.roadmap}' if region.carbon_scheme.roadmap else ''}

When answering:
- Reference specific data points (company names, figures, dates)
- Cite regulatory references specific to {region.name}
- Highlight compliance risks and patterns
- Use {region.currency} for monetary values
- Be concise but thorough
{data_note}

DATA CONTEXT:
{{context}}
""".format(context=context)
