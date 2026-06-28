"""Playwright-based PDF report generation for country briefs."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy.orm import Session

from atlas_api.models import Report

log = structlog.get_logger()

REPORTS_DIR = Path(os.getenv("ATLAS_REPORTS_DIR", "/tmp/atlas_reports"))

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #ffffff;
    color: #1a2a40;
    font-size: 10pt;
    line-height: 1.5;
  }
  .header {
    background: #0e1523;
    color: #fff;
    padding: 20px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .header-brand { font-size: 18pt; font-weight: 700; color: #f59e0b; letter-spacing: 0.05em; }
  .header-sub { font-size: 8pt; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 2px; }
  .header-meta { text-align: right; font-size: 8.5pt; color: #94a3b8; }
  .header-meta strong { color: #e2e8f0; font-size: 10pt; }
  .body { padding: 24px 28px; }
  .section { margin-bottom: 22px; }
  .section-title {
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    color: #64748b;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    margin-bottom: 12px;
  }
  .kpi-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .kpi {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
  }
  .kpi-label { font-size: 7.5pt; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 2px; }
  .kpi-value { font-size: 14pt; font-weight: 700; color: #0f172a; }
  .kpi-sub { font-size: 7.5pt; color: #94a3b8; margin-top: 1px; }
  .risk-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.04em;
  }
  .risk-low { background: #dcfce7; color: #15803d; }
  .risk-medium { background: #fef3c7; color: #b45309; }
  .risk-high { background: #fee2e2; color: #b91c1c; }
  .risk-critical { background: #4c0519; color: #fca5a5; }
  .row { display: flex; gap: 16px; }
  .col { flex: 1; }
  .ratings-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .rating-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
    text-align: center;
  }
  .rating-agency { font-size: 7.5pt; color: #64748b; text-transform: uppercase; letter-spacing: 0.08em; }
  .rating-value { font-size: 18pt; font-weight: 800; color: #0f172a; line-height: 1.2; }
  .rating-outlook { font-size: 8pt; color: #64748b; }
  .info-table { width: 100%; border-collapse: collapse; font-size: 9pt; }
  .info-table td { padding: 5px 0; border-bottom: 1px solid #f1f5f9; }
  .info-table td:first-child { color: #64748b; width: 40%; }
  .info-table td:last-child { font-weight: 500; color: #0f172a; }
  .commentary {
    background: #f0f9ff;
    border-left: 3px solid #0ea5e9;
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    font-size: 9pt;
    color: #0c4a6e;
    line-height: 1.6;
  }
  .footer {
    margin-top: 24px;
    border-top: 1px solid #e2e8f0;
    padding-top: 12px;
    font-size: 7.5pt;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
  }
  .risk-score-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .risk-number { font-size: 32pt; font-weight: 800; color: #0f172a; line-height: 1; }
  .dimension-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 8.5pt; }
  .dim-label { width: 130px; color: #334155; }
  .dim-bar-bg { flex: 1; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
  .dim-bar { height: 100%; border-radius: 3px; }
  .dim-score { width: 28px; text-align: right; color: #64748b; font-size: 8pt; }
  @media print {
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  }
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="header-brand">ATLAS</div>
    <div class="header-sub">Sovereign Finance Intelligence Platform</div>
  </div>
  <div class="header-meta">
    <strong>{{ country_name }} ({{ iso3 }})</strong><br>
    Country Brief &mdash; {{ generated_date }}<br>
    {{ region }} &bull; Tier {{ tier }}
  </div>
</div>

<div class="body">

  <!-- Risk Overview -->
  <div class="section">
    <div class="section-title">Composite Risk Assessment</div>
    <div class="risk-score-row">
      <div class="risk-number">{{ risk_score }}</div>
      <span class="risk-badge risk-{{ risk_level_cls }}">{{ risk_label }}</span>
    </div>
    {% if dimensions %}
    {% for dim in dimensions %}
    <div class="dimension-row">
      <span class="dim-label">{{ dim.label }}</span>
      <div class="dim-bar-bg">
        <div class="dim-bar" style="width: {{ dim.pct }}%; background: {{ dim.color }};"></div>
      </div>
      <span class="dim-score">{{ dim.score }}</span>
    </div>
    {% endfor %}
    {% endif %}
  </div>

  <div class="row">
    <div class="col">
      <!-- Macro KPIs -->
      <div class="section">
        <div class="section-title">Key Macro Indicators</div>
        <div class="kpi-grid">
          {% for tile in macro_tiles %}
          <div class="kpi">
            <div class="kpi-label">{{ tile.label }}</div>
            <div class="kpi-value">{% if tile.value is not none %}{{ tile.value }}{% if tile.unit %}{{ tile.unit }}{% endif %}{% else %}—{% endif %}</div>
            {% if tile.period %}<div class="kpi-sub">{{ tile.period }}</div>{% endif %}
          </div>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>

  <!-- Sovereign Ratings -->
  {% if ratings %}
  <div class="section">
    <div class="section-title">Sovereign Credit Ratings</div>
    <div class="ratings-grid">
      {% for r in ratings %}
      <div class="rating-card">
        <div class="rating-agency">{{ r.agency }}</div>
        <div class="rating-value">{{ r.rating }}</div>
        <div class="rating-outlook">{{ r.outlook or '—' }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <!-- Country Info -->
  <div class="section">
    <div class="section-title">Country Snapshot</div>
    <table class="info-table">
      <tr><td>Capital</td><td>{{ capital }}</td></tr>
      <tr><td>Region</td><td>{{ region }}</td></tr>
      <tr><td>Coverage Tier</td><td>Tier {{ tier }}</td></tr>
      <tr><td>Status</td><td>{{ status }}</td></tr>
      {% if spread_bps %}<tr><td>Atlas Spread</td><td>{{ spread_bps }} bps</td></tr>{% endif %}
    </table>
  </div>

  <!-- AI Debt Commentary -->
  {% if ai_commentary %}
  <div class="section">
    <div class="section-title">Debt Intelligence Note</div>
    <div class="commentary">{{ ai_commentary }}</div>
  </div>
  {% endif %}

  <div class="footer">
    <span>ATLAS &bull; Sovereign Finance Intelligence &bull; Confidential</span>
    <span>Generated {{ generated_date }} &bull; For institutional use only</span>
  </div>
</div>
</body>
</html>
"""


def _risk_class(label: str) -> str:
    mapping = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high", "CRITICAL": "critical"}
    return mapping.get(label.upper(), "medium")


def _bar_color(score: float) -> str:
    if score >= 75:
        return "#dc2626"
    if score >= 50:
        return "#f59e0b"
    return "#22c55e"


def _risk_label_from_score(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def _build_context(session: Session, iso3: str) -> dict[str, Any]:
    from atlas_api.services.country.bundle import get_country_bundle

    bundle = get_country_bundle(session, iso3)
    if bundle is None:
        raise ValueError(f"Country {iso3} not found")

    country = bundle.country
    risk = bundle.risk

    ctx: dict[str, Any] = {
        "iso3": iso3,
        "country_name": country.name,
        "capital": country.capital,
        "region": country.region,
        "tier": country.tier,
        "status": country.status.value if hasattr(country.status, "value") else str(country.status),
        "generated_date": datetime.now(UTC).strftime("%d %b %Y"),
        "risk_score": "—",
        "risk_label": "UNKNOWN",
        "risk_level_cls": "medium",
        "dimensions": [],
        "macro_tiles": [],
        "ratings": [],
        "ai_commentary": None,
        "spread_bps": None,
    }

    # risk.composite is a plain float
    if risk:
        score = risk.composite
        label = _risk_label_from_score(score)
        ctx["risk_score"] = f"{score:.0f}"
        ctx["risk_label"] = label
        ctx["risk_level_cls"] = _risk_class(label)

        dim_labels = {
            "debt_burden": "Debt Burden",
            "external_liquidity": "External Liquidity",
            "fiscal_flexibility": "Fiscal Flexibility",
            "growth_momentum": "Growth Momentum",
            "inflation_pressure": "Inflation Pressure",
            "fx_stability": "FX Stability",
        }
        for d in risk.dimensions[:6]:
            dim_key = d.dimension.value if hasattr(d.dimension, "value") else str(d.dimension)
            # scores are 0–10; scale to 0–100 for bar width
            pct = min(d.score * 10, 100)
            ctx["dimensions"].append({
                "label": dim_labels.get(dim_key, dim_key.replace("_", " ").title()),
                "score": str(d.score),
                "pct": pct,
                "color": _bar_color(pct),
            })

    if bundle.macro:
        priority = [
            "GDP_GROWTH_PCT", "INFLATION_PCT", "FISCAL_BALANCE_PCT_GDP",
            "CURRENT_ACCOUNT_PCT_GDP", "PUBLIC_DEBT_PCT_GDP", "UNEMPLOYMENT_PCT",
        ]
        unit_map = {
            "GDP_GROWTH_PCT": "%", "INFLATION_PCT": "%",
            "FISCAL_BALANCE_PCT_GDP": "% GDP", "CURRENT_ACCOUNT_PCT_GDP": "% GDP",
            "PUBLIC_DEBT_PCT_GDP": "% GDP", "UNEMPLOYMENT_PCT": "%",
        }
        label_map = {
            "GDP_GROWTH_PCT": "GDP Growth", "INFLATION_PCT": "Inflation",
            "FISCAL_BALANCE_PCT_GDP": "Fiscal Balance", "CURRENT_ACCOUNT_PCT_GDP": "Current Account",
            "PUBLIC_DEBT_PCT_GDP": "Debt/GDP", "UNEMPLOYMENT_PCT": "Unemployment",
        }
        tile_map = {
            (t.indicator.value if hasattr(t.indicator, "value") else str(t.indicator)): t
            for t in bundle.macro
        }
        for ind in priority:
            t = tile_map.get(ind)
            if t and t.value is not None:
                ctx["macro_tiles"].append({
                    "label": label_map.get(ind, ind),
                    "value": f"{t.value:+.1f}" if t.value < 0 else f"{t.value:.1f}",
                    "unit": unit_map.get(ind, ""),
                    "period": t.period,
                })

    # ratings.latest_per_agency is dict[str, RatingAction]
    if bundle.ratings and bundle.ratings.latest_per_agency:
        for agency, r in bundle.ratings.latest_per_agency.items():
            ctx["ratings"].append({
                "agency": agency,
                "rating": r.rating,
                "outlook": r.outlook,
            })

    if bundle.debt_profile and isinstance(bundle.debt_profile, dict):
        ctx["ai_commentary"] = bundle.debt_profile.get("ai_commentary")

    return ctx


def _render_html(ctx: dict[str, Any]) -> str:
    from jinja2 import Environment

    env = Environment(autoescape=True)
    tmpl = env.from_string(_HTML_TEMPLATE)
    return tmpl.render(**ctx)


def generate_country_brief(
    session: Session,
    iso3: str,
    user_id: uuid.UUID | None,
) -> Report:
    """Create a pending Report, generate PDF with Playwright, update status and return."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report = Report(
        id=uuid.uuid4(),
        template="country_brief",
        iso3=iso3,
        generated_by=user_id,
        status="pending",
    )
    session.add(report)
    session.flush()

    pdf_path = REPORTS_DIR / f"{report.id}.pdf"

    try:
        ctx = _build_context(session, iso3)
        html = _render_html(ctx)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
                print_background=True,
            )
            browser.close()

        report.pdf_path = str(pdf_path)
        report.status = "ready"
        report.manifest = {"template": "country_brief", "iso3": iso3}
        log.info("report_generated", iso3=iso3, report_id=str(report.id))

    except Exception:
        log.exception("report_generation_failed", iso3=iso3, report_id=str(report.id))
        report.status = "failed"

    session.commit()
    return report


def list_reports(session: Session, iso3: str | None = None) -> list[Report]:
    q = session.query(Report).order_by(Report.generated_at.desc())
    if iso3:
        q = q.filter(Report.iso3 == iso3.upper())
    return q.limit(100).all()


def get_report(session: Session, report_id: uuid.UUID) -> Report | None:
    return session.get(Report, report_id)
