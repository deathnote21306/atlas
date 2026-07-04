"""Generate AI-written analyst narratives for scenario impact cards."""

from __future__ import annotations

import structlog
from atlas_schemas.scenario import CountryImpact, ShockVector
from pydantic import BaseModel

from atlas_api.services.ai.provider import call_tool

log = structlog.get_logger()

_SYSTEM_PROMPT = """You are a sovereign-finance analyst at a multilateral development institution.
Given a macro shock scenario and its computed impact on each country, write a 2–3 sentence
narrative for each country that reads like an analyst note — specific, direct, and grounded
in the numbers. Reflect what the shock actually means for that economy (e.g. an oil price
crash hits exporters differently than importers). Vary the language across countries so the
notes feel individually written, not templated. No hedging filler like "it is worth noting."
Use the fiscal, external, and debt deltas and risk change provided. Never fabricate numbers
not in the input."""


class _CountryNarrative(BaseModel):
    iso3: str
    narrative: str


class _NarrativeOutput(BaseModel):
    countries: list[_CountryNarrative]


def _shock_description(shocks: ShockVector) -> str:
    parts = []
    if shocks.commodity_shock != 0:
        direction = "surge" if shocks.commodity_shock > 0 else "crash"
        parts.append(
            f"oil/commodity price {direction}"
            f" ({shocks.commodity_shock:+.0f} USD/bbl equivalent)"
        )
    if shocks.gdp_shock != 0:
        parts.append(f"global GDP growth shock ({shocks.gdp_shock:+.1f}pp)")
    if shocks.rate_shock != 0:
        parts.append(f"EM spread widening ({shocks.rate_shock * 100:+.0f}bps)")
    if shocks.fx_depreciation != 0:
        parts.append(f"USD appreciation / EM FX depreciation ({shocks.fx_depreciation:+.1f}%)")
    if shocks.inflation_shock != 0:
        parts.append(f"global trade volume shift ({shocks.inflation_shock:+.1f}pp)")
    return "; ".join(parts) if parts else "baseline (no active shocks)"


def generate_scenario_narratives(
    shocks: ShockVector,
    impacts: list[CountryImpact],
) -> dict[str, str] | None:
    """Call Claude once to generate analyst narratives for all countries.

    Returns iso3 → narrative dict, or None if the AI call fails.
    """
    shock_desc = _shock_description(shocks)

    country_blocks = []
    for imp in impacts:
        country_blocks.append(
            f"- {imp.name} ({imp.iso3}): risk {imp.baseline_risk:.1f} → {imp.new_risk:.1f} "
            f"({imp.risk_change:+.1f} pts) | fiscal {imp.deltas.fiscal_balance:+.2f}pp | "
            f"external {imp.deltas.current_account:+.2f}pp | debt/GDP {imp.deltas.debt_gdp:+.2f}pp"
        )

    user_msg = (
        f"SCENARIO: {shock_desc}\n\n"
        f"COUNTRY IMPACTS:\n" + "\n".join(country_blocks) + "\n\n"
        "Write a 2–3 sentence analyst narrative for each country above."
    )

    result, meta = call_tool(
        messages=[{"role": "user", "content": user_msg}],
        system=_SYSTEM_PROMPT,
        tool_name="scenario_narratives",
        tool_description="Return analyst-quality impact narratives for each country",
        result_model=_NarrativeOutput,
        max_tokens=1800,
    )

    if result is None:
        log.warning("scenario_narratives_failed", error=meta.get("error"))
        return None

    return {c.iso3: c.narrative for c in result.countries}
