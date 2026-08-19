"""Cheap deterministic pre-filters that run before any paid AI call.

This module deliberately makes no editorial judgement. It removes only articles
that are obviously off-topic, and it caps how many items reach the grader. Every
ambiguous article is passed through, because the AI grader is the component that
is allowed to decide what is relevant.
"""

from __future__ import annotations

from typing import TypeVar

TRACKED_ISO3: frozenset[str] = frozenset(
    {"CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"}
)

# Narrow on purpose. A term belongs here only if it cannot plausibly appear in a
# sovereign macro story.
_JUNK_TERMS: frozenset[str] = frozenset(
    {
        "afcon",
        "premier league",
        "world cup",
        "quarter final",
        "semi final",
        "full time",
        "kick off",
        "goalkeeper",
        "striker",
        "midfielder",
        "nollywood",
        "bollywood",
        "box office",
        "red carpet",
        "new album",
        "obituary",
        "funeral service",
        "horoscope",
        "recipe",
        "celebrity gossip",
    }
)

T = TypeVar("T")


def is_obvious_junk(title: str, body: str) -> bool:
    """True only for articles that clearly cannot bear on sovereign risk."""
    combined = f"{title} {body}".lower()
    return any(term in combined for term in _JUNK_TERMS)


def split_by_budget(items: list[T], limit: int) -> tuple[list[T], list[T]]:
    """Split into the items to grade now and the items deferred to a later run."""
    if limit <= 0:
        return [], list(items)
    return list(items[:limit]), list(items[limit:])
