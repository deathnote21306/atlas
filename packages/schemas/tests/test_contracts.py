from atlas_schemas.health import HealthResponse


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
    from pydantic import ValidationError
    from atlas_schemas.country import Country

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
