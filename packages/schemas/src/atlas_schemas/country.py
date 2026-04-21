from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class CountryStatus(StrEnum):
    PERFORMING = "performing"
    NEGOTIATING = "negotiating"
    SELECTIVE_DEFAULT = "selective_default"
    DEFAULT = "default"
    RESTRUCTURED = "restructured"


class FxRegime(StrEnum):
    FLOAT = "float"
    MANAGED_FLOAT = "managed_float"
    PEGGED = "pegged"
    CRAWLING_PEG = "crawling_peg"
    BASKET_PEG = "basket_peg"
    CURRENCY_BOARD = "currency_board"
    NO_SEPARATE_LEGAL_TENDER = "no_separate_legal_tender"


class CompositeRisk(BaseModel):
    score: int
    label: str
    trend: str
    as_of: str | None = None


class AtlasSpread(BaseModel):
    value_bps: int
    as_of: str | None = None


class ImfProgram(BaseModel):
    code: str
    status: str


class Country(BaseModel):
    iso3: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    name: str
    capital: str
    region: str
    tags: list[str]
    tier: str
    status: CountryStatus
    fx_regime: FxRegime
    fx_regime_notes: str | None = None
    fx_parallel_premium: float | None = None
    iso_code_short: str | None = None
    sub_region: str | None = None
    status_tags: list[str] | None = None
    context_tags: list[str] | None = None
    composite_risk: CompositeRisk | None = None
    atlas_spread: AtlasSpread | None = None
    imf_program: ImfProgram | None = None
    key_risks: list[str] | None = None
    key_opportunities: list[str] | None = None
    risk_decomposition: dict | None = None
    macro_annotations: dict[str, str] | None = None
    primary_currency: str | None = None
    fx_intelligence: dict | None = None
    economic_structure: dict | None = None
    forecasts: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def _assemble_nested(cls, data: dict | object) -> dict | object:
        """Map flat DB columns to nested objects when deserializing from ORM."""
        if isinstance(data, dict):
            raw = data
        elif hasattr(data, "__dict__"):
            raw = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
        else:
            return data

        if "composite_risk" not in raw and raw.get("composite_risk_score") is not None:
            as_of = raw.get("composite_risk_as_of")
            raw["composite_risk"] = CompositeRisk(
                score=raw["composite_risk_score"],
                label=raw.get("composite_risk_label", ""),
                trend=raw.get("composite_risk_trend", "stable"),
                as_of=as_of.isoformat() if as_of else None,
            )

        if "atlas_spread" not in raw and raw.get("atlas_spread_bps") is not None:
            as_of = raw.get("atlas_spread_as_of")
            raw["atlas_spread"] = AtlasSpread(
                value_bps=raw["atlas_spread_bps"],
                as_of=as_of.isoformat() if as_of else None,
            )

        if "imf_program" not in raw and raw.get("imf_program_code") is not None:
            raw["imf_program"] = ImfProgram(
                code=raw["imf_program_code"],
                status=raw.get("imf_program_status", ""),
            )

        if "fx_intelligence" not in raw and raw.get("primary_currency") is not None:
            ccy = raw["primary_currency"]
            regime = raw.get("fx_regime", "")
            regime_labels = {
                "float": "Free Float",
                "managed_float": "Managed Float",
                "crawling_peg": "Crawling Peg",
                "pegged": "Hard Peg",
                "basket_peg": "Managed Float",
                "currency_board": "Currency Board",
            }

            pp_val = raw.get("fx_parallel_premium")
            pp_severity = "—"
            if pp_val is not None:
                pp_val = float(pp_val)
                if pp_val > 25:
                    pp_severity = "CRITICAL"
                elif pp_val > 10:
                    pp_severity = "ELEVATED"
                elif pp_val > 2:
                    pp_severity = "NOTABLE"
                else:
                    pp_severity = "TIGHT"

            reer = raw.get("fx_reer_deviation_pct")
            reer_label = "—"
            if reer is not None:
                reer = float(reer)
                if reer > 10:
                    reer_label = "overvalued"
                elif reer > -10:
                    reer_label = "fair value"
                elif reer > -25:
                    reer_label = "undervalued"
                else:
                    reer_label = "extreme undervaluation"

            reer_as_of = raw.get("fx_reer_as_of")
            change_as_of = raw.get("fx_change_as_of")
            intervention = raw.get("fx_last_bc_intervention")

            raw["fx_intelligence"] = {
                "pair": f"USD/{ccy}",
                "regime": str(regime) if regime else None,
                "regime_label": regime_labels.get(str(regime), str(regime)),
                "change_ladder": {
                    "1d": float(raw["fx_change_1d_pct"])
                    if raw.get("fx_change_1d_pct") is not None
                    else None,
                    "1w": float(raw["fx_change_1w_pct"])
                    if raw.get("fx_change_1w_pct") is not None
                    else None,
                    "1m": float(raw["fx_change_1m_pct"])
                    if raw.get("fx_change_1m_pct") is not None
                    else None,
                    "3m": float(raw["fx_change_3m_pct"])
                    if raw.get("fx_change_3m_pct") is not None
                    else None,
                    "as_of": change_as_of.isoformat() if change_as_of else None,
                },
                "implied_vol": {
                    "value": float(raw["fx_implied_vol_pct"])
                    if raw.get("fx_implied_vol_pct") is not None
                    else None,
                    "note": raw.get("fx_implied_vol_note"),
                },
                "parallel_premium": {
                    "value_pct": pp_val,
                    "severity": pp_severity,
                },
                "reer_deviation": {
                    "value_pct": reer,
                    "label": reer_label,
                    "as_of": reer_as_of.isoformat() if reer_as_of else None,
                    "source": raw.get("reer_source", "seed"),
                    "base_period": raw.get("reer_base_period", "2010"),
                },
                "reserves_usd_bn": None,
                "last_bc_intervention": intervention.isoformat() if intervention else None,
            }

        return raw
