"""Input provenance tracking for risk decomposition."""

from __future__ import annotations

from typing import Any

INPUT_PROVENANCE: dict[str, str] = {
    "fiscal_balance_pct_gdp": "real",
    "external_debt_pct_gdp": "real",
    "revenue_quality_flag": "seeded",
    "fx_reserves_usd_bn": "real",
    "import_cover_months": "computed",
    "external_restructuring_flag": "seeded",
    "fx_parallel_premium_pct": "seeded",
    "fx_reer_deviation_pct": "dynamic",
    "fx_implied_vol_pct": "seeded",
    "fx_regime": "seeded",
    "fx_market_liquidity_flag": "seeded",
    "real_gdp_growth_pct": "real",
    "gdp_volatility_5yr": "computed",
    "data_quality_flag": "seeded",
    "political_stability_index": "seeded",
    "active_conflict_flag": "seeded",
    "imf_program_active": "real",
    "imf_program_type": "real",
    "market_access_flag": "seeded",
    "restructuring_overhang_flag": "seeded",
}


def make_input(key: str, value: Any, source: str, provenance_override: str | None = None) -> dict[str, Any]:
    prov = provenance_override or INPUT_PROVENANCE.get(key, "seeded")
    if value is None:
        prov = "missing"
    return {"key": key, "value": value, "source": source, "provenance": prov}


def summarize_provenance(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"real": 0, "seeded": 0, "computed": 0, "missing": 0}
    seeded_keys = []
    for inp in inputs:
        p = inp.get("provenance", "missing")
        counts[p] = counts.get(p, 0) + 1
        if p == "seeded":
            seeded_keys.append(inp["key"])
    return {
        "total_inputs": len(inputs),
        **counts,
        "seeded_inputs": seeded_keys,
    }
