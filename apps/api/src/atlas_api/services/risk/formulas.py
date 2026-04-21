"""Deterministic risk dimension formulas.

Each function returns { score: int 0-100, inputs: list[dict], edge_case: bool }.
"""

from __future__ import annotations

from typing import Any

from atlas_api.services.risk.provenance import make_input


def _clip(val: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, val))


def fiscal_risk(
    fiscal_balance_pct_gdp: float | None,
    external_debt_pct_gdp: float | None,
    revenue_quality_flag: str,
) -> dict[str, Any]:
    fb = fiscal_balance_pct_gdp or 0
    ed = external_debt_pct_gdp or 0
    # v2.1: increased debt multiplier 0.5→0.8 and base 30→35 to better separate
    # distressed (ETH ed=24 → ~54) from stable (MAR ed=45 → ~71 pre-quality).
    # Calibrated on ETH fiscal target=68.
    base = _clip(35 + (-fb * 4) + (ed * 0.8))

    edge_case = False
    if revenue_quality_flag == "low":
        score = min(base * 1.15, 100)
        edge_case = base * 1.15 > 100
    else:
        score = base

    inputs = [
        make_input("fiscal_balance_pct_gdp", fiscal_balance_pct_gdp, "imf_weo"),
        make_input("external_debt_pct_gdp", external_debt_pct_gdp, "worldbank"),
        make_input("revenue_quality_flag", revenue_quality_flag, "atlas_seed"),
    ]
    return {"score": round(score), "inputs": inputs, "edge_case": edge_case}


def external_risk(
    import_cover_months: float | None,
    external_restructuring_flag: bool,
    fx_parallel_premium_pct: float | None,
    fx_reserves_usd_bn: float | None,
) -> dict[str, Any]:
    cover = import_cover_months or 0
    premium = fx_parallel_premium_pct or 0

    reserves_component = _clip(100 - (cover * 15))
    restructuring_component = 30 if external_restructuring_flag else 0
    premium_component = min(premium * 0.8, 30)
    score = _clip(reserves_component + restructuring_component + premium_component)

    inputs = [
        make_input("fx_reserves_usd_bn", fx_reserves_usd_bn, "worldbank"),
        make_input("import_cover_months", import_cover_months, "computed", "computed"),
        make_input("external_restructuring_flag", external_restructuring_flag, "atlas_seed"),
        make_input("fx_parallel_premium_pct", fx_parallel_premium_pct, "atlas_seed"),
    ]
    return {"score": round(score), "inputs": inputs, "edge_case": external_restructuring_flag}


def fx_risk(
    fx_parallel_premium_pct: float | None,
    fx_reer_deviation_pct: float | None,
    fx_implied_vol_pct: float | None,
    fx_regime: str | None,
    fx_market_liquidity_flag: str,
    reer_provenance: str = "seeded",
) -> dict[str, Any]:
    premium = fx_parallel_premium_pct or 0
    reer_dev = fx_reer_deviation_pct or 0
    regime = fx_regime or "managed_float"

    premium_component = min(premium * 1.5, 40)
    reer_component = min(abs(reer_dev) * 0.6, 30)
    regime_map = {
        "pegged": 0,
        "hard_peg": 0,
        "currency_board": 0,
        "managed_float": 10,
        "basket_peg": 8,
        "float": 5,
        "crawling_peg": 15,
        "multiple_regime": 25,
    }
    regime_component = regime_map.get(regime, 10)
    liquidity_map = {"liquid": 0, "thin": 10, "illiquid": 20}
    liquidity_component = liquidity_map.get(fx_market_liquidity_flag, 10)

    score = _clip(premium_component + reer_component + regime_component + liquidity_component)

    inputs = [
        make_input("fx_parallel_premium_pct", fx_parallel_premium_pct, "atlas_seed"),
        make_input("fx_reer_deviation_pct", fx_reer_deviation_pct, "imf_ifs", reer_provenance),
        make_input("fx_implied_vol_pct", fx_implied_vol_pct, "atlas_seed"),
        make_input("fx_regime", fx_regime, "atlas_seed"),
        make_input("fx_market_liquidity_flag", fx_market_liquidity_flag, "atlas_seed"),
    ]
    edge_case = fx_market_liquidity_flag == "illiquid" or premium > 25
    return {"score": round(score), "inputs": inputs, "edge_case": edge_case}


def growth_risk(
    real_gdp_growth_pct: float | None,
    gdp_volatility_5yr: float | None,
    data_quality_flag: str,
) -> dict[str, Any]:
    growth = real_gdp_growth_pct or 0
    vol = gdp_volatility_5yr or 0

    # v2.1: reduced growth discount 6→5 and increased volatility weight 5→7
    # to better reflect that high-growth conflict-affected countries still have
    # elevated risk. Calibrated on ETH growth target=60.
    growth_component = _clip(60 - (growth * 5))
    volatility_component = min(vol * 7, 25)
    quality_penalty = (
        15 if data_quality_flag == "low" else (5 if data_quality_flag == "medium" else 0)
    )

    score = _clip(growth_component + volatility_component + quality_penalty)

    inputs = [
        make_input("real_gdp_growth_pct", real_gdp_growth_pct, "imf_weo"),
        make_input("gdp_volatility_5yr", gdp_volatility_5yr, "computed", "computed"),
        make_input("data_quality_flag", data_quality_flag, "atlas_seed"),
    ]
    return {"score": round(score), "inputs": inputs, "edge_case": False}


def political_risk(
    political_stability_index: float,
    active_conflict_flag: bool,
    imf_program_active: bool,
) -> dict[str, Any]:
    stability_component = _clip(50 - (political_stability_index * 20))
    conflict_component = 20 if active_conflict_flag else 0
    imf_anchor_discount = -10 if imf_program_active else 0

    score = _clip(stability_component + conflict_component + imf_anchor_discount)

    inputs = [
        make_input("political_stability_index", political_stability_index, "atlas_seed"),
        make_input("active_conflict_flag", active_conflict_flag, "atlas_seed"),
        make_input("imf_program_active", imf_program_active, "atlas_api"),
    ]
    return {"score": round(score), "inputs": inputs, "edge_case": active_conflict_flag}


def liquidity_risk(
    market_access_flag: str,
    fx_reserves_usd_bn: float | None,
    imf_program_type: str | None,
    restructuring_overhang_flag: bool,
    pod_override_active: bool,
) -> dict[str, Any]:
    reserves = fx_reserves_usd_bn or 0

    access_map = {"full": 20, "limited": 50, "none": 80}
    access_component = access_map.get(market_access_flag, 50)
    reserves_component = _clip(20 - reserves * 2, 0, 20)
    imf_anchor_discount = -5 if imf_program_type else 0
    restructuring_overhang = 15 if restructuring_overhang_flag else 0

    score = _clip(
        access_component + reserves_component + imf_anchor_discount + restructuring_overhang
    )

    if pod_override_active:
        score = max(score, 95)
        edge_case = True
    else:
        edge_case = market_access_flag == "none" or restructuring_overhang_flag

    inputs = [
        make_input("market_access_flag", market_access_flag, "atlas_seed"),
        make_input("fx_reserves_usd_bn", fx_reserves_usd_bn, "worldbank"),
        make_input("imf_program_type", imf_program_type, "atlas_api"),
        make_input("restructuring_overhang_flag", restructuring_overhang_flag, "atlas_seed"),
    ]
    return {"score": round(score), "inputs": inputs, "edge_case": edge_case}
