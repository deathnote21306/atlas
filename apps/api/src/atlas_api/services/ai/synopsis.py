"""Grounded country synopsis generation using Claude.

1. Pull latest macro bundle + last 7d scored news + ratings + FX
2. Build structured context prompt
3. Call Claude with typed output schema
4. Persist synopsis with approval_state=proposed + prompt_trace
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import NewsImpactScore, NewsItem, Synopsis
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.ai.trace import persist_trace
from atlas_api.services.country.bundle import get_country_bundle
from atlas_schemas.ai import SynopsisContent

log = structlog.get_logger()

_SYSTEM_PROMPT = """You are a sovereign-finance intelligence analyst producing concise country
risk synopses for institutional investors and multilateral stakeholders.

Your synopsis must be grounded ONLY in the structured context provided.
Do not speculate beyond the data. If coverage is thin, note it in coverage_notes.

Write 2-4 paragraphs covering:
1. Macro snapshot: GDP trajectory, fiscal/debt position, inflation
2. External & FX: current account, reserves, currency dynamics
3. Political & ratings: governance signals, rating actions, outlook
4. Near-term risks and opportunities from recent news

Be factual, precise, and use numerical values from the context."""


def _get_recent_news(session: Session, iso3: str, days: int = 7) -> list[dict]:
    """Pull scored news items from the last N days for a country."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    items = (
        session.query(NewsItem, NewsImpactScore)
        .outerjoin(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        .filter(NewsItem.primary_iso3 == iso3)
        .filter(NewsItem.ingested_at >= cutoff)
        .order_by(NewsItem.ingested_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for item, score in items:
        entry: dict[str, Any] = {
            "title": item.title,
            "source": item.source,
            "published_at": str(item.published_at) if item.published_at else None,
            "event_type": item.event_type,
        }
        if score:
            entry["impact"] = {
                "fiscal": score.fiscal_impact,
                "external": score.external_impact,
                "fx": score.fx_impact,
                "political": score.political_impact,
            }
        result.append(entry)
    return result


def _build_grounding_context(session: Session, iso3: str) -> dict[str, Any]:
    """Assemble the structured grounding block for the prompt."""
    bundle = get_country_bundle(session, iso3)
    if bundle is None:
        return {}

    context: dict[str, Any] = {
        "country": {
            "iso3": bundle.country.iso3,
            "name": bundle.country.name,
            "region": bundle.country.region,
            "status": bundle.country.status,
            "fx_regime": bundle.country.fx_regime,
        },
        "macro": [
            {
                "indicator": t.indicator,
                "label": t.label,
                "value": t.value,
                "period": t.period,
                "source": t.source,
            }
            for t in bundle.macro
            if t.value is not None
        ],
        "ratings": {
            agency: {
                "rating": r.rating,
                "outlook": r.outlook,
                "action": r.action,
                "action_date": str(r.action_date),
            }
            for agency, r in bundle.ratings.latest_per_agency.items()
        },
        "risk_composite": bundle.risk.composite,
    }

    if bundle.fx is not None:
        context["fx"] = {
            "ccy": bundle.fx.latest.ccy,
            "usd_per_ccy": bundle.fx.latest.usd_per_ccy,
            "observation_date": str(bundle.fx.latest.observation_date),
            "delta_7d_pct": bundle.fx.delta_7d_pct,
            "delta_30d_pct": bundle.fx.delta_30d_pct,
        }

    context["recent_news"] = _get_recent_news(session, iso3)
    return context


def generate_synopsis(
    session: Session,
    iso3: str,
    *,
    user_id: uuid.UUID | None = None,
) -> Synopsis | None:
    """Generate a synopsis for a country using Claude.

    Returns the persisted Synopsis with approval_state='proposed',
    or None if AI is unavailable.
    """
    iso3 = iso3.upper()

    if not settings.anthropic_api_key:
        log.info("synopsis_skip_no_api_key", iso3=iso3)
        return None

    # Build grounding context
    context = _build_grounding_context(session, iso3)
    if not context:
        log.warning("synopsis_skip_no_bundle", iso3=iso3)
        return None

    context_str = json.dumps(context, indent=2, default=str)
    messages = [
        {
            "role": "user",
            "content": (
                f"Generate a country risk synopsis for {iso3} based on the following data.\n\n"
                f"STRUCTURED CONTEXT:\n```json\n{context_str}\n```"
            ),
        }
    ]

    input_hash = compute_input_hash(context)

    result, meta = call_tool(
        messages=messages,
        system=_SYSTEM_PROMPT,
        tool_name="generate_synopsis",
        tool_description="Generate a grounded country risk synopsis",
        result_model=SynopsisContent,
        max_tokens=4096,
    )

    if result is None:
        log.info("synopsis_ai_unavailable", iso3=iso3, error=meta.get("error"))
        return None

    # Persist prompt trace
    trace = persist_trace(
        session,
        purpose="synopsis",
        model=meta["model"],
        prompt_hash=meta["prompt_hash"],
        input_hash=input_hash,
        input_data={"system": _SYSTEM_PROMPT, "messages": messages},
        output_data=result.model_dump(),
        tokens_in=meta["tokens_in"],
        tokens_out=meta["tokens_out"],
        user_id=user_id,
        approval_state="proposed",
    )

    # Persist synopsis
    synopsis = Synopsis(
        id=uuid.uuid4(),
        iso3=iso3,
        text=result.text,
        key_points=[kp.model_dump() for kp in result.key_points],
        generated_at=datetime.now(UTC),
        prompt_trace_id=trace.id,
        approval_state="proposed",
    )
    session.add(synopsis)
    session.commit()

    log.info("synopsis_generated", iso3=iso3, synopsis_id=str(synopsis.id))
    return synopsis
