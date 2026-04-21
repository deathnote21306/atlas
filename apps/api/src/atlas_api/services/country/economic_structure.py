"""Build economic_structure object for a country from trade_annual data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from atlas_api.models import TradeAnnual


def get_economic_structure(session: Session, iso3: str) -> dict[str, Any] | None:
    """Build the economic_structure response object."""
    # Find latest year with data
    latest_year = session.execute(
        select(func.max(TradeAnnual.year))
        .where(TradeAnnual.reporter_iso3 == iso3)
    ).scalar()

    if latest_year is None:
        return None

    year = latest_year

    # Top exports (by commodity, partner=World/NULL)
    export_rows = session.execute(
        select(TradeAnnual)
        .where(
            TradeAnnual.reporter_iso3 == iso3,
            TradeAnnual.year == year,
            TradeAnnual.flow == "X",
            TradeAnnual.commodity_code.isnot(None),
            TradeAnnual.partner_iso3.is_(None),
        )
        .order_by(desc(TradeAnnual.trade_value_usd))
        .limit(5)
    ).scalars().all()

    exports_total = sum(r.trade_value_usd or 0 for r in export_rows)
    # Get actual total from all commodity rows
    all_export_val = session.execute(
        select(func.sum(TradeAnnual.trade_value_usd))
        .where(
            TradeAnnual.reporter_iso3 == iso3,
            TradeAnnual.year == year,
            TradeAnnual.flow == "X",
            TradeAnnual.commodity_code.isnot(None),
            TradeAnnual.partner_iso3.is_(None),
        )
    ).scalar() or exports_total

    top_exports = []
    for i, r in enumerate(export_rows):
        share = (r.trade_value_usd / all_export_val * 100) if all_export_val > 0 else 0
        top_exports.append({
            "rank": i + 1,
            "commodity_code": r.commodity_code,
            "commodity_label": r.commodity_label,
            "value_usd": r.trade_value_usd,
            "share_pct": round(share, 1),
        })

    # Top import sources (by partner, commodity=NULL)
    import_rows = session.execute(
        select(TradeAnnual)
        .where(
            TradeAnnual.reporter_iso3 == iso3,
            TradeAnnual.year == year,
            TradeAnnual.flow == "M",
            TradeAnnual.partner_iso3.isnot(None),
            TradeAnnual.commodity_code.is_(None),
        )
        .order_by(desc(TradeAnnual.trade_value_usd))
        .limit(3)
    ).scalars().all()

    all_import_val = session.execute(
        select(func.sum(TradeAnnual.trade_value_usd))
        .where(
            TradeAnnual.reporter_iso3 == iso3,
            TradeAnnual.year == year,
            TradeAnnual.flow == "M",
            TradeAnnual.partner_iso3.isnot(None),
            TradeAnnual.commodity_code.is_(None),
        )
    ).scalar() or 1

    top_import_sources = []
    for i, r in enumerate(import_rows):
        share = (r.trade_value_usd / all_import_val * 100) if all_import_val > 0 else 0
        top_import_sources.append({
            "rank": i + 1,
            "partner_iso3": r.partner_iso3,
            "partner_name": r.partner_name,
            "value_usd": r.trade_value_usd,
            "share_pct": round(share, 1),
        })

    # Top trade partners (exports + imports combined)
    export_by_partner = {}
    export_partner_rows = session.execute(
        select(TradeAnnual)
        .where(
            TradeAnnual.reporter_iso3 == iso3,
            TradeAnnual.year == year,
            TradeAnnual.flow == "X",
            TradeAnnual.partner_iso3.isnot(None),
            TradeAnnual.commodity_code.is_(None),
        )
    ).scalars().all()
    for r in export_partner_rows:
        export_by_partner[r.partner_iso3] = (r.trade_value_usd or 0, r.partner_name)

    import_by_partner = {}
    import_partner_rows = session.execute(
        select(TradeAnnual)
        .where(
            TradeAnnual.reporter_iso3 == iso3,
            TradeAnnual.year == year,
            TradeAnnual.flow == "M",
            TradeAnnual.partner_iso3.isnot(None),
            TradeAnnual.commodity_code.is_(None),
        )
    ).scalars().all()
    for r in import_partner_rows:
        import_by_partner[r.partner_iso3] = (r.trade_value_usd or 0, r.partner_name)

    all_partners = set(export_by_partner) | set(import_by_partner)
    partner_totals = []
    for p in all_partners:
        exp_val, exp_name = export_by_partner.get(p, (0, None))
        imp_val, imp_name = import_by_partner.get(p, (0, None))
        name = exp_name or imp_name or p
        partner_totals.append((p, name, exp_val, imp_val, exp_val + imp_val))

    partner_totals.sort(key=lambda x: x[4], reverse=True)

    top_trade_partners = []
    for i, (iso, name, exp, imp, total) in enumerate(partner_totals[:5]):
        top_trade_partners.append({
            "rank": i + 1,
            "partner_iso3": iso,
            "partner_name": name,
            "exports_usd": exp,
            "imports_usd": imp,
            "total_usd": total,
        })

    return {
        "year": year,
        "as_of_note": "Latest Comtrade annual data",
        "diversification_score": None,
        "diversification_hhi": None,
        "commodity_dependency_pct": None,
        "exports_total_usd": all_export_val,
        "imports_total_usd": all_import_val,
        "top_exports": top_exports,
        "top_import_sources": top_import_sources,
        "top_trade_partners": top_trade_partners,
    }
