"""One structured Claude call that grades a single news article.

Relevance, country attribution, translation, classification and impact are judged
together in a single call, because they all depend on the same reading of the
article. Splitting them would cost more and agree less.
"""

from __future__ import annotations

from typing import Any

import structlog
from atlas_schemas.ai import NewsGradeResult

from atlas_api.config import settings
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.news.prefilter import TRACKED_ISO3

log = structlog.get_logger()

SYSTEM_PROMPT = """You grade news articles for Atlas, a sovereign risk platform for \
institutional analysts covering ten African economies: Cote d'Ivoire (CIV), Ghana (GHA), \
Kenya (KEN), Nigeria (NGA), Senegal (SEN), Ethiopia (ETH), Rwanda (RWA), South Africa (ZAF), \
Morocco (MAR) and Egypt (EGY).

IN SCOPE: sovereign debt, IMF programmes, rating actions, fiscal and monetary policy, FX, \
reserves, bonds and eurobonds, growth, inflation, material trade and investment flows, and \
politics that materially affects creditworthiness such as elections, coups, sanctions, major \
reform and significant unrest.

OUT OF SCOPE: sport, entertainment, crime reporting, general human interest, routine corporate \
news with no sovereign read-through, and politics with no plausible link to creditworthiness.

RULES:
1. Set relevant to true only if the article is in scope. When uncertain, prefer false and give \
a low relevance_score rather than admitting weak material.
2. primary_iso3 is the single country the article is actually about. If a country appears only \
as a passing comparison or background mention, it is NOT the primary country. If no tracked \
country is the real subject, return null.
3. secondary_iso3 lists other tracked countries the article genuinely covers, not mentions.
4. rationale is one sentence, grounded in the article, explaining the decision.
5. title_en and summary_en must always be English. Translate faithfully when the source is not \
English. Never invent detail that is not in the article.
6. source_lang is the ISO 639-1 code of the original article.
7. relevance_score reflects both importance to sovereign risk and your confidence.
"""


def _build_messages(
    title: str, body: str, source: str, candidate_iso3: str | None
) -> list[dict[str, Any]]:
    candidate_line = (
        f"A keyword pre-pass guessed the country may be {candidate_iso3}. "
        "Treat this as a hint only and override it if the article says otherwise."
        if candidate_iso3
        else "The keyword pre-pass produced no country guess."
    )
    return [
        {
            "role": "user",
            "content": (
                f"Source: {source}\n"
                f"Title: {title}\n"
                f"Body: {body[:2000]}\n\n"
                f"{candidate_line}\n\n"
                "Grade this article using the grade_news_article tool."
            ),
        }
    ]


def grade_article(
    *,
    title: str,
    body: str,
    source: str,
    candidate_iso3: str | None,
) -> tuple[NewsGradeResult | None, dict[str, Any]]:
    """Grade one article. Returns (result, meta). Result is None on any failure."""
    if not settings.anthropic_api_key:
        log.debug("news_grader_no_api_key")
        return None, {"error": "no_api_key"}

    messages = _build_messages(title, body, source, candidate_iso3)
    grounding = {"title": title, "body": body[:2000], "source": source}

    result, meta = call_tool(
        messages=messages,
        system=SYSTEM_PROMPT,
        tool_name="grade_news_article",
        tool_description=(
            "Judge one news article for sovereign risk relevance, attribute it to the "
            "correct country, translate it to English, classify it and score its impact"
        ),
        result_model=NewsGradeResult,
        max_tokens=1024,
    )
    meta["input_hash"] = compute_input_hash(grounding)

    if result is None:
        log.info("news_grade_failed", error=meta.get("error"), title=title[:80])

    return result, meta


def passes_gate(result: NewsGradeResult, threshold: int) -> bool:
    """The keep rule: on policy, confident enough, and about a tracked country."""
    return (
        result.relevant
        and result.relevance_score >= threshold
        and result.primary_iso3 is not None
        and result.primary_iso3 in TRACKED_ISO3
    )
