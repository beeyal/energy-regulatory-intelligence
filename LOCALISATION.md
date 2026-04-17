# Localisation Guide

This guide explains how to adapt the Energy Compliance Intelligence Hub for a new APJ market.

## Architecture Overview

All market configuration lives in `app/server/region_data.py` (source of truth) and is exposed via `/api/regions`. The frontend reads this at startup via `RegionContext`, making `activeMarket` (including `currency`) available to every component through the `useRegion()` hook.

Currency formatting is centralised in `app/frontend/src/utils/currency.ts`. No component should hardcode `$` or `en-AU` — all monetary values route through `formatCurrency()` or `formatCurrencyFull()`.

---

## Adding or Updating a Market

### 1. Edit `app/server/region_data.py`

Add or update the market entry under the `MARKETS` dict:

```python
"SG": {
    "name": "Singapore",
    "flag": "🇸🇬",
    "currency": "SGD",          # ISO 4217 code — must match currency.ts
    "market_name": "Singapore Energy Market",
    "data_available": True,     # Set False until data is loaded
    "regulators": [
        {"code": "EMA", "name": "Energy Market Authority", "domain": "Electricity & Gas"},
        {"code": "NEA", "name": "National Environment Agency", "domain": "Carbon & Environment"},
    ],
    "carbon_scheme": {
        "name": "Carbon Tax (CMS)",
        "operator": "IRAS / NEA",
        "threshold_kt": 25,
        "price_unit": "SGD/tCO2-e",
        "price": 25.0,
        "roadmap": "S$50–80/tCO2-e by 2030",
    },
    "key_legislation": [
        "Electricity Act (Cap. 89A)",
        "Gas Act (Cap. 116A)",
        "Carbon Pricing Act 2018",
    ],
    "known_companies": ["SP Group", "Sembcorp", "Keppel Electric", "Genco 1"],
    "system_prompt_context": "You are an expert in Singapore energy market regulations...",
},
```

Key fields:

| Field | Required | Notes |
|---|---|---|
| `currency` | Yes | ISO 4217 code. Must have a matching symbol in `currency.ts` |
| `data_available` | Yes | Controls LLM data-vs-knowledge routing and UI "Live Data" badge |
| `known_companies` | Yes | Used by the synthetic data generator for enforcement/obligation records |
| `regulators` | Yes | Drives filter pills and narrative context |
| `carbon_scheme.price` | Yes | Used in Emissions Forecaster shortfall cost calculations |

### 2. Add currency symbol to `app/frontend/src/utils/currency.ts`

If the currency is not already in `CURRENCY_SYMBOLS`:

```typescript
const CURRENCY_SYMBOLS: Record<string, string> = {
  // ... existing entries ...
  MYR: "RM",    // example: Malaysian ringgit
};
```

Also add a locale entry in `CURRENCY_LOCALE` inside `formatCurrencyFull()`:

```typescript
MYR: "ms-MY",
```

### 3. Load data (optional but recommended)

Without `data_available: true`, the LLM will answer from general knowledge and the enforcement/obligation tables will show AU placeholder data. To load real data:

1. Add a CSV for enforcement actions to `app/server/data/` (schema: same columns as `aer_enforcement_actions.csv`)
2. Register it in `app/server/in_memory_data.py` under the market's key
3. Set `data_available: True` in `region_data.py`

If real data is unavailable, the synthetic generator in `in_memory_data.py` (`_generate_synthetic_obligations`) will produce plausible obligations using the market's `known_companies` and `regulators` lists. Increase `count` or diversify companies in `known_companies` to improve data density.

---

## Supported Markets (Current)

| Code | Market | Currency | Data |
|------|--------|----------|------|
| AU | Australia (NEM) | AUD | Live (real AER/CER/AEMO data) |
| SG | Singapore | SGD | Synthetic |
| NZ | New Zealand | NZD | Synthetic |
| JP | Japan | JPY | Synthetic |
| IN | India | INR | Synthetic |
| KR | South Korea | KRW | Synthetic |
| TH | Thailand | THB | Synthetic |
| PH | Philippines | PHP | Synthetic |

---

## Currency Formatting Rules

| Currency | Symbol | Notes |
|---|---|---|
| AUD | A$ | Abbreviated: A$1.2M |
| SGD | S$ | Abbreviated: S$1.2M |
| NZD | NZ$ | Abbreviated: NZ$1.2M |
| JPY | ¥ | No decimal fraction (integer yen) |
| INR | ₹ | en-IN locale (uses lakh/crore grouping in full format) |
| KRW | ₩ | No decimal fraction |
| THB | ฿ | Abbreviated: ฿1.2M |
| PHP | ₱ | Abbreviated: ₱1.2M |

Use `formatCurrency(val, currency)` for abbreviated display (stat cards, table cells).  
Use `formatCurrencyFull(val, currency)` for full unabbreviated amounts (penalty totals, legal filings).

---

## LLM Prompt Localisation

The LLM is instructed to use the market's currency and local regulatory context automatically via `build_system_prompt()` in `app/server/region.py`. No prompt changes are needed when adding a new market — only `region_data.py` needs updating.

To verify: switch to the new market in the UI and open the AI Chat panel. The assistant should reference local regulators, currency, and legislation without prompting.

---

## Testing a New Market

1. Start the app locally: `cd app && uvicorn server.main:app --reload`
2. Open the region switcher and select the new market
3. Verify:
   - All monetary values show the correct currency symbol
   - The Board Briefing header shows the correct market name and flag
   - The AI Chat responds with local regulatory context
   - The Obligation Register shows records with the correct regulator codes
   - The Emissions Forecaster shows costs in the correct currency
