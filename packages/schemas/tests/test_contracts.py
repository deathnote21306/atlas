import uuid
from datetime import UTC, datetime

from atlas_schemas.health import HealthResponse
from atlas_schemas.news import EventType, ImpactLevel, NewsImpactScoreOut, NewsItemOut


def test_health_response_roundtrips():
    payload = {"status": "ok", "version": "0.0.0"}
    obj = HealthResponse.model_validate(payload)
    assert obj.status == "ok"
    assert obj.version == "0.0.0"
    assert obj.model_dump() == payload


def test_health_response_rejects_unknown_status():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        HealthResponse.model_validate({"status": "bogus", "version": "0.0.0"})


def test_country_schema_roundtrip():
    from atlas_schemas.country import Country, CountryStatus, FxRegime

    payload = {
        "iso3": "GHA",
        "name": "Ghana",
        "capital": "Accra",
        "region": "West Africa",
        "tags": ["SSA", "commodities"],
        "tier": "B",
        "status": "negotiating",
        "fx_regime": "float",
        "fx_regime_notes": None,
        "fx_parallel_premium": None,
    }
    c = Country.model_validate(payload)
    assert c.iso3 == "GHA"
    assert c.status is CountryStatus.NEGOTIATING
    assert c.fx_regime is FxRegime.FLOAT


def test_country_rejects_bad_iso3():
    import pytest
    from atlas_schemas.country import Country
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Country.model_validate({
            "iso3": "GH",
            "name": "Ghana",
            "capital": "Accra",
            "region": "West Africa",
            "tags": [],
            "tier": "B",
            "status": "negotiating",
            "fx_regime": "float",
            "fx_regime_notes": None,
            "fx_parallel_premium": None,
        })


def test_data_vintage_schema_roundtrip():
    from atlas_schemas.ingestion import DataVintage

    v = DataVintage.model_validate({
        "id": "00000000-0000-0000-0000-000000000001",
        "created_at": "2026-04-16T03:00:00Z",
        "source": "nightly",
        "notes": None,
    })
    assert v.source == "nightly"


def test_macro_value_schema():
    from atlas_schemas.macro import MacroIndicator, MacroValue
    v = MacroValue.model_validate({
        "iso3": "GHA",
        "indicator": "INFLATION_PCT",
        "period": "2024",
        "value": 22.4,
        "source": "worldbank",
        "source_date": "2024-12-31",
        "ingested_at": "2026-04-16T03:00:00Z",
        "vintage_id": "00000000-0000-0000-0000-000000000001",
    })
    assert v.indicator is MacroIndicator.INFLATION_PCT
    assert v.value == 22.4


def test_macro_value_allows_null():
    from atlas_schemas.macro import MacroValue
    v = MacroValue.model_validate({
        "iso3": "GHA", "indicator": "GDP_USD", "period": "2025", "value": None,
        "source": "imf_weo", "source_date": None,
        "ingested_at": "2026-04-16T03:00:00Z",
        "vintage_id": "00000000-0000-0000-0000-000000000001",
    })
    assert v.value is None


def test_rating_action_schema():
    from atlas_schemas.ratings import Agency, RatingAction
    r = RatingAction.model_validate({
        "iso3": "GHA", "agency": "S&P", "rating": "SD",
        "outlook": None, "action": "default", "action_date": "2022-12-21",
        "source_url": "https://www.spglobal.com/ratings/en/research/articles/221221",
    })
    assert r.agency is Agency.SP


def test_staleness_info_schema():
    from atlas_schemas.staleness import StalenessInfo, StalenessState
    s = StalenessInfo.model_validate({"state": "yellow", "age_days": 200})
    assert s.state is StalenessState.YELLOW
    assert s.age_days == 200
    s_missing = StalenessInfo.model_validate({"state": "missing", "age_days": None})
    assert s_missing.state is StalenessState.MISSING
    assert s_missing.age_days is None


def test_dimension_score_schema():
    from atlas_schemas.risk import DimensionScore, RiskDimension
    d = DimensionScore.model_validate({
        "dimension": "debt_burden", "score": 7, "rationale": "debt 85% of GDP",
        "input_value": 85.0, "is_estimate": False,
    })
    assert d.dimension is RiskDimension.DEBT_BURDEN
    assert d.score == 7


def test_country_bundle_shape():
    from atlas_schemas.bundle import CountryBundle
    payload = {
        "country": {
            "iso3": "GHA", "name": "Ghana", "capital": "Accra", "region": "West Africa",
            "tags": ["SSA"], "tier": "C", "status": "restructured", "fx_regime": "float",
            "fx_regime_notes": None, "fx_parallel_premium": None,
        },
        "macro": [], "fx": None,
        "ratings": {"latest_per_agency": {}, "composite_score": None, "history": []},
        "risk": {"composite": 50.0, "dimensions": []},
        "synopsis": None, "news_placeholder": True,
    }
    b = CountryBundle.model_validate(payload)
    assert b.country.iso3 == "GHA"
    assert b.risk.composite == 50.0


def test_shock_vector_defaults():
    from atlas_schemas.scenario import ShockVector
    sv = ShockVector()
    assert sv.gdp_shock == 0.0
    assert sv.fx_depreciation == 0.0


def test_shock_vector_roundtrip():
    from atlas_schemas.scenario import ShockVector
    sv = ShockVector(gdp_shock=-2.0, inflation_shock=5.0, fx_depreciation=15.0,
                     rate_shock=3.0, commodity_shock=-10.0)
    d = sv.model_dump()
    assert ShockVector(**d) == sv


def test_scenario_preview_roundtrip():
    from atlas_schemas.scenario import ScenarioDeltas, ScenarioPreview
    sp = ScenarioPreview(
        baseline_risk_score=46.7, new_risk_score=53.3, distress_probability=0.2624,
        deltas=ScenarioDeltas(debt_gdp=3.06, fiscal_balance=-1.5, current_account=-1.5),
        baseline_debt_gdp=60.0, baseline_fiscal_balance=-3.0, baseline_current_account=-2.0,
        new_debt_gdp=63.06, new_fiscal_balance=-4.5, new_current_account=-3.5,
    )
    d = sp.model_dump()
    assert ScenarioPreview(**d).new_risk_score == 53.3


# -- News schemas ----------------------------------------------------------


def test_event_type_values():
    assert EventType.MONETARY == "Monetary"
    assert EventType.FISCAL == "Fiscal"
    assert EventType.POLITICAL == "Political"
    assert EventType.EXTERNAL == "External"
    assert EventType.RATING == "Rating"
    assert EventType.IMF == "IMF"
    assert EventType.MARKET == "Market"


def test_impact_level_values():
    assert ImpactLevel.LOW == "L"
    assert ImpactLevel.MEDIUM == "M"
    assert ImpactLevel.HIGH == "H"


def test_news_item_out_roundtrip():
    now = datetime.now(UTC)
    item = NewsItemOut(
        id=uuid.uuid4(),
        url="https://example.com/article",
        title="Kenya raises rates",
        source="Reuters",
        published_at=now,
        primary_iso3="KEN",
        event_type="Monetary",
        ingested_at=now,
        impact_score=None,
    )
    d = item.model_dump()
    assert NewsItemOut(**d).title == "Kenya raises rates"


def test_news_impact_score_out_roundtrip():
    now = datetime.now(UTC)
    score = NewsImpactScoreOut(
        id=uuid.uuid4(),
        news_item_id=uuid.uuid4(),
        fiscal_impact=ImpactLevel.LOW,
        external_impact=ImpactLevel.MEDIUM,
        fx_impact=ImpactLevel.HIGH,
        political_impact=ImpactLevel.LOW,
        rationale={"keywords": ["rate hike", "inflation"]},
        scorer="heuristic",
        scored_at=now,
    )
    d = score.model_dump()
    assert NewsImpactScoreOut(**d).fiscal_impact == "L"


def test_news_item_with_score():
    now = datetime.now(UTC)
    item_id = uuid.uuid4()
    item = NewsItemOut(
        id=item_id,
        url="https://example.com/article2",
        title="Nigeria fiscal deficit widens",
        source="IMF Blog",
        published_at=now,
        primary_iso3="NGA",
        event_type="Fiscal",
        ingested_at=now,
        impact_score=NewsImpactScoreOut(
            id=uuid.uuid4(),
            news_item_id=item_id,
            fiscal_impact=ImpactLevel.HIGH,
            external_impact=ImpactLevel.MEDIUM,
            fx_impact=ImpactLevel.MEDIUM,
            political_impact=ImpactLevel.LOW,
            rationale={"keywords": ["deficit", "spending"]},
            scorer="heuristic",
            scored_at=now,
        ),
    )
    assert item.impact_score is not None
    assert item.impact_score.fiscal_impact == "H"


# -- AI schemas ------------------------------------------------------------


def test_synopsis_content_roundtrip():
    from atlas_schemas.ai import SynopsisContent, SynopsisKeyPoint
    sc = SynopsisContent(
        text="Nigeria faces headwinds...",
        key_points=[SynopsisKeyPoint(text="Naira under pressure", category="fx")],
        coverage_notes=["Q4 GDP not yet available"],
    )
    d = sc.model_dump()
    assert d["text"] == "Nigeria faces headwinds..."
    assert len(d["key_points"]) == 1
    rt = SynopsisContent.model_validate(d)
    assert rt == sc


def test_ai_score_result_roundtrip():
    from atlas_schemas.ai import AIScoreResult
    r = AIScoreResult(
        fiscal_impact="H", external_impact="M", fx_impact="L", political_impact="M",
        rationale={"fiscal": "Debt restructuring", "external": "Trade deficit",
                   "fx": "Stable peg", "political": "Election upcoming"},
    )
    d = r.model_dump()
    assert d["fiscal_impact"] == "H"
    rt = AIScoreResult.model_validate(d)
    assert rt == r


def test_synopsis_approval_state_is_strenum():
    from atlas_schemas.ai import SynopsisApprovalState
    assert SynopsisApprovalState.PROPOSED == "proposed"
    assert SynopsisApprovalState.HUMAN_APPROVED == "human_approved"
