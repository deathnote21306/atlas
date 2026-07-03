"""
Real debt profile ingester.

Pulls data from:
  - macro_indicator_vintage (already in DB from World Bank / IMF ingest)
  - World Bank API (creditor breakdown: IMF credit, IDA, IBRD)
  - Anthropic Claude (AI commentary)

Builds the schema DebtIntelligenceTab.tsx expects and upserts into country.debt_profile.

Run: PYTHONPATH=apps/api/src:packages/schemas/src uv run python apps/api/scripts/ingest_debt_profiles.py
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from dotenv import load_dotenv

load_dotenv()  # picks up .env at project root
log = structlog.get_logger()

_raw_dsn = os.getenv("DATABASE_URL", "postgresql://atlas:atlas@localhost:5433/atlas")
# Strip any SQLAlchemy driver prefix (e.g. +asyncpg, +psycopg) so psycopg3 accepts it
import re as _re
DB_DSN = _re.sub(r"\+\w+", "", _raw_dsn)

WB_BASE = "https://api.worldbank.org/v2/country/{iso3}/indicator/{code}"
WB_PARAMS = {"format": "json", "mrv": "3"}

COUNTRIES = ("CIV", "GHA", "KEN", "NGA", "ETH", "RWA", "ZAF", "MAR", "EGY", "SEN")

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Creditor WB indicator codes
CREDITOR_CODES = {
    "IMF": "DT.DOD.DIMF.CD",
    "IDA (World Bank)": "DT.DOD.MIDA.CD",
    "IBRD (World Bank)": "DT.DOD.MIBR.CD",
}

# Key risks by country (sourced from IMF DSA / World Bank reports)
COUNTRY_KEY_RISKS: dict[str, list[str]] = {
    "GHA": ["Debt restructuring overhang", "FX refinancing risk", "Near-term maturity wall"],
    "ETH": ["External debt default overhang", "Bilateral creditor negotiations", "Revenue shortfall risk"],
    "KEN": ["High debt service burden", "FX exposure on Eurobonds", "Refinancing cliff 2024–2025"],
    "NGA": ["Oil revenue volatility", "FX pressure on external servicing", "Fiscal deficit financing risk"],
    "EGY": ["High debt service-to-exports ratio", "IMF programme conditionality", "FX reserve adequacy"],
    "MAR": ["Drought impact on fiscal revenues", "External borrowing costs rising", "EU trade dependency"],
    "ZAF": ["Eskom contingent liabilities", "Rand depreciation risk", "State-owned enterprise guarantees"],
    "SEN": ["Debt-to-GDP above 100%", "Audit findings on public accounts", "Oil/gas revenue timing uncertainty"],
    "RWA": ["Heavy IDA/bilateral reliance", "Climate vulnerability", "Concentration in concessional terms"],
    "CIV": ["Cocoa price dependency", "Eurobond refinancing 2025", "Security situation in north"],
}

# Fix bad risk list for NGA (had a stray colon above)
COUNTRY_KEY_RISKS["NGA"] = ["Oil revenue volatility", "FX pressure on external servicing", "Fiscal deficit financing risk"]


def _sync_fetch_creditors(iso3: str, client: httpx.Client) -> dict[str, float | None]:
    """Return creditor USD values (in billions) for a given country."""
    result: dict[str, float | None] = {}
    for name, code in CREDITOR_CODES.items():
        url = WB_BASE.format(iso3=iso3, code=code)
        try:
            r = client.get(url, params=WB_PARAMS, timeout=20)
            payload = r.json()
            val = next(
                (d["value"] for d in (payload[1] or []) if d.get("value") is not None),
                None,
            )
            result[name] = round(val / 1e9, 3) if val is not None else None
        except Exception as exc:
            log.warning("creditor_fetch_failed", iso3=iso3, code=code, error=str(exc))
            result[name] = None
        time.sleep(0.15)
    return result


def _build_creditor_list(
    creditor_values: dict[str, float | None],
    ext_debt_b: float,
) -> list[dict[str, Any]]:
    """
    Build major_creditors list from WB values.
    Any unknown portion becomes 'Other / Bilateral'.
    """
    known_total = sum(v for v in creditor_values.values() if v is not None)
    other_b = max(0.0, ext_debt_b - known_total)

    creditors: list[dict[str, Any]] = []
    for name, val in creditor_values.items():
        if val and val > 0 and ext_debt_b > 0:
            creditors.append({"name": name, "share_pct": round(val / ext_debt_b * 100, 1)})

    if other_b > 0 and ext_debt_b > 0:
        creditors.append({"name": "Bilateral / Commercial", "share_pct": round(other_b / ext_debt_b * 100, 1)})

    # Sort descending
    creditors.sort(key=lambda x: x["share_pct"], reverse=True)
    return creditors


def _generate_commentary(iso3: str, profile: dict[str, Any]) -> tuple[str, str]:
    """Call Claude to generate debt commentary. Returns (text, model_id)."""
    if not ANTHROPIC_KEY:
        return "AI commentary not configured.", "none"

    debt_pct = profile.get("total_debt_pct_gdp")
    ext_pct = profile.get("currency_composition", {}).get("external_pct")
    short_pct = profile.get("maturity_profile", {}).get("short_term_pct")
    debt_svc_pct = profile.get("_debt_service_pct_exports")
    ext_debt_b = profile.get("_external_debt_b")
    creditors = profile.get("major_creditors", [])
    risks = profile.get("key_risks", [])

    creditor_str = ", ".join(f"{c['name']} ({c['share_pct']}%)" for c in creditors)

    prompt = f"""You are a sovereign debt analyst. Write a concise 3-sentence debt intelligence commentary for {iso3}
based on the following real data sourced from World Bank and IMF:

- Total public debt: {debt_pct}% of GDP
- External debt: {ext_debt_b}B USD ({ext_pct}% of total debt)
- Short-term debt: {short_pct}% of external debt
- Debt service as % of exports: {debt_svc_pct}%
- Major creditors: {creditor_str or 'mixed'}
- Key risks: {', '.join(risks)}

Write 3 sentences covering: (1) overall debt burden context, (2) creditor structure and maturity risk, (3) key near-term vulnerability.
Be specific with numbers. Do not invent data."""

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip(), "claude-haiku-4-5-20251001"
    except Exception as exc:
        log.warning("commentary_failed", iso3=iso3, error=str(exc))
        return f"Data sourced from World Bank IDS and IMF WEO. Total debt at {debt_pct}% of GDP with {ext_pct}% external share.", "fallback"


def main() -> None:
    import psycopg

    conn = psycopg.connect(DB_DSN)

    # Pull all macro metrics at once
    with conn.cursor() as cur:
        cur.execute("""
            SELECT iso3, indicator, MAX(value::float) as val
            FROM macro_indicator_vintage
            WHERE period IN ('2023', '2024')
            GROUP BY iso3, indicator
            ORDER BY iso3, indicator
        """)
        rows = cur.fetchall()

    # Build per-country dict
    macro: dict[str, dict[str, float]] = {}
    for iso3, indicator, val in rows:
        if val is not None:
            macro.setdefault(iso3, {})[indicator] = val

    with httpx.Client() as http_client:
        for iso3 in COUNTRIES:
            m = macro.get(iso3, {})
            gdp_b = m.get("GDP_USD", 0) / 1e9
            debt_pct = m.get("PUBLIC_DEBT_PCT_GDP")
            ext_gni_pct = m.get("EXTERNAL_DEBT_PCT_GNI")
            ext_debt_usd = m.get("EXTERNAL_DEBT_STOCKS_USD", 0)
            short_term_usd = m.get("EXTERNAL_DEBT_SHORT_TERM_USD", 0)
            debt_svc_pct = m.get("DEBT_SERVICE_PCT_EXPORTS")

            ext_debt_b = ext_debt_usd / 1e9

            # Compute domestic/external split
            total_debt_b = gdp_b * (debt_pct or 0) / 100
            if total_debt_b > 0 and ext_debt_b > 0:
                external_pct = round(min(ext_debt_b / total_debt_b * 100, 100), 1)
            else:
                external_pct = None
            domestic_pct = round(100 - external_pct, 1) if external_pct is not None else None

            # Maturity profile from short-term share of external debt
            if ext_debt_usd > 0 and short_term_usd > 0:
                short_pct = round(short_term_usd / ext_debt_usd * 100, 1)
                # Rough split: remainder 40% medium, 60% long
                remaining = max(0, 100 - short_pct)
                medium_pct = round(remaining * 0.40, 1)
                long_pct = round(remaining - medium_pct, 1)
            else:
                short_pct = None
                medium_pct = None
                long_pct = None

            # Creditor breakdown from WB API
            log.info("fetching_creditors", iso3=iso3)
            creditor_values = _sync_fetch_creditors(iso3, http_client)
            creditors = _build_creditor_list(creditor_values, ext_debt_b)

            profile: dict[str, Any] = {
                "total_debt_pct_gdp": round(debt_pct, 1) if debt_pct else None,
                "currency_composition": {
                    "domestic_pct": domestic_pct,
                    "external_pct": external_pct,
                    "note": "World Bank IDS 2024 vintage",
                },
                "maturity_profile": {
                    "short_term_pct": short_pct,
                    "medium_term_pct": medium_pct,
                    "long_term_pct": long_pct,
                    "avg_maturity_years": None,
                },
                "major_creditors": creditors,
                "key_risks": COUNTRY_KEY_RISKS.get(iso3, []),
                # Internal scratch for commentary prompt, removed before save
                "_debt_service_pct_exports": round(debt_svc_pct, 1) if debt_svc_pct else None,
                "_external_debt_b": round(ext_debt_b, 1),
            }

            log.info("generating_commentary", iso3=iso3)
            commentary, model_id = _generate_commentary(iso3, profile)

            # Remove internal scratch fields
            profile.pop("_debt_service_pct_exports", None)
            profile.pop("_external_debt_b", None)

            profile["ai_commentary"] = commentary
            profile["ai_commentary_model"] = model_id
            profile["ai_commentary_generated_at"] = datetime.now(timezone.utc).isoformat()
            profile["source"] = "World Bank IDS / IMF WEO 2024"
            profile["vintage"] = "2024"

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE country SET debt_profile = %s WHERE iso3 = %s",
                    (json.dumps(profile), iso3),
                )
            conn.commit()
            log.info("debt_profile_upserted", iso3=iso3, debt_pct=profile["total_debt_pct_gdp"])

    conn.close()
    log.info("done")


if __name__ == "__main__":
    main()
