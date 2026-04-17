"""
Region configuration for multi-market support.
Data lives in region_data.py as a plain Python dict — no external dependencies.
"""

from functools import lru_cache
from pydantic import BaseModel

from .region_data import MARKETS


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


@lru_cache(maxsize=32)
def get_region(market_code: str) -> RegionConfig:
    """Return RegionConfig for a market code. Falls back to AU if unknown."""
    code = (market_code or "AU").upper()
    raw = MARKETS.get(code) or MARKETS["AU"]
    return RegionConfig(code=code if code in MARKETS else "AU", **raw)


def list_markets() -> list[dict[str, str]]:
    """Return summary list of all markets for the region switcher API."""
    return [
        {
            "code": code,
            "name": info["name"],
            "flag": info["flag"],
            "market_name": info["market_name"],
            "currency": info.get("currency", "AUD"),
            "data_available": str(info.get("data_available", False)).lower(),
        }
        for code, info in MARKETS.items()
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

    return (
        f"{region.system_prompt_context}\n\n"
        f"REGULATORS:\n{regulators}\n\n"
        f"KEY LEGISLATION:\n{legislation}\n\n"
        f"CARBON SCHEME: {region.carbon_scheme.name}\n"
        f"  Operator: {region.carbon_scheme.operator}\n"
        f"  Price: {region.currency} {region.carbon_scheme.price}"
        f" per {region.carbon_scheme.price_unit.split('/')[-1]}\n"
        + (f"  Roadmap: {region.carbon_scheme.roadmap}\n" if region.carbon_scheme.roadmap else "")
        + f"\nWhen answering:\n"
        f"- Reference specific data points (company names, figures, dates)\n"
        f"- Cite regulatory references specific to {region.name}\n"
        f"- Use {region.currency} for monetary values\n"
        f"- Be concise but thorough\n"
        f"{data_note}\n\n"
        f"DATA CONTEXT:\n{context}"
    )
