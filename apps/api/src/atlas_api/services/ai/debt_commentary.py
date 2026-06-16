"""Generate AI commentary for a country's debt profile using Claude."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import Country
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.ai.trace import persist_trace

log = structlog.get_logger()

_SYSTEM_PROMPT = """You are a sovereign-finance analyst. Given a country's structured debt profile,
write 2-3 sentences of concise, factual commentary for institutional investors.
Focus on the most material risks: FX exposure, maturity concentration, restructuring
overhang, and market access constraints. Use numbers from the data. No speculation."""


class _DebtCommentary(BaseModel):
    commentary: str


def generate_debt_commentary(session: Session, iso3: str) -> bool:
    """Generate and persist AI commentary into country.debt_profile['ai_commentary'].

    Returns True if commentary was written, False if skipped.
    """
    iso3 = iso3.upper()

    if not settings.anthropic_api_key:
        log.info("debt_commentary_skip_no_api_key", iso3=iso3)
        return False

    country = session.get(Country, iso3)
    if country is None or country.debt_profile is None:
        log.info("debt_commentary_skip_no_profile", iso3=iso3)
        return False

    profile = country.debt_profile
    context_str = json.dumps(profile, indent=2, default=str)
    messages = [
        {
            "role": "user",
            "content": (
                f"Write debt intelligence commentary for {iso3}.\n\n"
                f"DEBT PROFILE:\n```json\n{context_str}\n```"
            ),
        }
    ]

    input_hash = compute_input_hash(profile)

    result, meta = call_tool(
        messages=messages,
        system=_SYSTEM_PROMPT,
        tool_name="generate_debt_commentary",
        tool_description="Generate concise debt intelligence commentary",
        result_model=_DebtCommentary,
        max_tokens=512,
    )

    if result is None:
        log.info("debt_commentary_ai_unavailable", iso3=iso3, error=meta.get("error"))
        return False

    persist_trace(
        session,
        purpose="debt_commentary",
        model=meta["model"],
        prompt_hash=meta["prompt_hash"],
        input_hash=input_hash,
        input_data={"system": _SYSTEM_PROMPT, "messages": messages},
        output_data={"commentary": result.commentary},
        tokens_in=meta["tokens_in"],
        tokens_out=meta["tokens_out"],
        user_id=None,
        approval_state="proposed",
    )

    updated_profile: dict[str, Any] = dict(profile)
    updated_profile["ai_commentary"] = result.commentary
    updated_profile["ai_commentary_generated_at"] = datetime.now(UTC).isoformat()
    updated_profile["ai_commentary_model"] = meta["model"]
    country.debt_profile = updated_profile
    session.commit()

    log.info("debt_commentary_generated", iso3=iso3)
    return True


def run_debt_commentary_for_all(session: Session) -> dict[str, bool]:
    """Run generate_debt_commentary for every country that has a debt_profile."""
    countries = session.query(Country).filter(Country.debt_profile.isnot(None)).all()
    results = {}
    for country in countries:
        try:
            results[country.iso3] = generate_debt_commentary(session, country.iso3)
        except Exception:
            log.exception("debt_commentary_failed", iso3=country.iso3)
            session.rollback()
            results[country.iso3] = False
    return results
