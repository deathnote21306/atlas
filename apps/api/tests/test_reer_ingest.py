"""Tests for the REER ingester against IMF's SDMX 2.1 EER API (api.imf.org).

The legacy dataservices.imf.org SDMX-JSON endpoint was decommissioned; the
ingester now targets the IMF.STA:EER dataflow which returns SDMX-ML
StructureSpecificData (XML), keyed COUNTRY.INDICATOR.FREQUENCY with ISO3
country codes and TIME_PERIOD like "2024-M04".
"""

from datetime import date

from atlas_api.ingestion import reer as reer_mod
from atlas_api.ingestion.reer import (
    IMF_REER_INDICATOR,
    _parse_eer_xml,
    fetch_imf_eer,
    run_reer_ingest,
)
from atlas_api.models import Country, REERHistory

# Faithful (trimmed) shape of a real api.imf.org EER response for GHA.
SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<message:StructureSpecificData
  xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"
  xmlns:ss="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/structurespecific">
  <message:DataSet>
    <Series COUNTRY="GHA" INDICATOR="REER_IX_RY2010_ACW_RCPI" FREQUENCY="M">
      <Obs TIME_PERIOD="2024-M01" OBS_VALUE="72.80737891050065" DERIVATION_TYPE="SE"/>
      <Obs TIME_PERIOD="2024-M02" OBS_VALUE="72.59413578695376" DERIVATION_TYPE="SE"/>
      <Obs TIME_PERIOD="2024-M03" OBS_VALUE="71.09889568125423" DERIVATION_TYPE="SE"/>
      <Obs TIME_PERIOD="2024-M04" OBS_VALUE="70.10552074579132" DERIVATION_TYPE="SE"/>
    </Series>
  </message:DataSet>
</message:StructureSpecificData>"""

# Header-only response (country with no EER coverage, e.g. KEN/ETH).
EMPTY_XML = """<?xml version='1.0' encoding='UTF-8'?>
<message:StructureSpecificData
  xmlns:message="http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message">
  <message:DataSet/>
</message:StructureSpecificData>"""


def test_parse_eer_xml_extracts_observations():
    obs = _parse_eer_xml(SAMPLE_XML)
    assert len(obs) == 4
    first = obs[0]
    assert first["period"] == date(2024, 1, 1)
    assert first["value"] == 72.80737891050065
    assert first["base_period"] == "2010"
    assert first["indicator"] == "REER_IX_RY2010_ACW_RCPI"
    # "-M" period separator handled (not "2024-04")
    assert obs[3]["period"] == date(2024, 4, 1)


def test_parse_eer_xml_empty_returns_nothing():
    assert _parse_eer_xml(EMPTY_XML) == []


def test_parse_eer_xml_malformed_returns_nothing():
    assert _parse_eer_xml("<not-xml") == []


def test_fetch_imf_eer_hits_new_endpoint_and_parses(httpx_mock):
    httpx_mock.add_response(text=SAMPLE_XML, is_reusable=True)
    obs = fetch_imf_eer("GHA")

    # Targets the new SDMX 2.1 EER dataflow on api.imf.org with ISO3 + REER indicator.
    req = httpx_mock.get_requests()[0]
    assert "api.imf.org" in str(req.url)
    assert "IMF.STA,EER" in str(req.url)
    assert f"GHA.{IMF_REER_INDICATOR}.M" in str(req.url)
    assert "dataservices.imf.org" not in str(req.url)

    assert len(obs) == 4
    assert obs[0]["source_series_id"] and "GHA" in obs[0]["source_series_id"]


def test_fetch_imf_eer_empty_coverage(httpx_mock):
    httpx_mock.add_response(text=EMPTY_XML, is_reusable=True)
    assert fetch_imf_eer("KEN") == []


def _seed_country(session, iso3="GHA"):
    session.add(
        Country(
            iso3=iso3, name="Ghana", capital="Accra", region="West Africa",
            tags=["SSA"], tier="C", status="restructured", fx_regime="float",
            fx_regime_notes=None, fx_parallel_premium=None,
        )
    )
    session.commit()


def test_run_reer_ingest_writes_rows_and_updates_country(session, monkeypatch):
    _seed_country(session, "GHA")

    obs = [
        {"period": date(2024, m, 1), "value": 70.0 + m, "base_period": "2010",
         "source_series_id": f"IMF.STA.EER.GHA.{IMF_REER_INDICATOR}.M"}
        for m in range(1, 5)
    ]
    monkeypatch.setattr(reer_mod, "fetch_imf_eer", lambda iso3, months_back=24: obs)

    stats = run_reer_ingest(session, countries=["GHA"])

    assert stats["countries_imf_eer"] == 1
    rows = session.query(REERHistory).filter_by(iso3="GHA").all()
    assert len(rows) >= 4
    assert all(r.source == "imf_eer" for r in rows)

    country = session.get(Country, "GHA")
    assert country.fx_reer_deviation_pct is not None
    assert country.fx_reer_as_of is not None


def test_run_reer_ingest_no_coverage_is_seed_only(session, monkeypatch):
    _seed_country(session, "GHA")
    monkeypatch.setattr(reer_mod, "fetch_imf_eer", lambda iso3, months_back=24: [])
    # BIS fallback also returns nothing in this isolated test.
    monkeypatch.setattr(reer_mod, "fetch_bis_bulk", lambda iso3_list: {i: [] for i in iso3_list})

    stats = run_reer_ingest(session, countries=["GHA"])

    assert stats["countries_imf_eer"] == 0
    assert stats["countries_seed_only"] == 1
