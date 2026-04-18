"""Synopsis endpoints: read (approved) + admin CRUD."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from atlas_schemas.ai import SynopsisListItem, SynopsisOut
from fastapi import APIRouter, HTTPException

from atlas_api.deps import CurrentUser, DbSession
from atlas_api.models import Synopsis
from atlas_api.services.ai.synopsis import generate_synopsis

router = APIRouter(tags=["synopses"])

_APPROVED_STATES = {"human_approved", "auto_approved_similarity", "auto_approved_stable_country"}


@router.get("/api/synopses/{iso3}")
def get_latest_synopsis(iso3: str, db: DbSession) -> SynopsisOut | None:
    """Return the latest approved synopsis for a country, or null."""
    iso3 = iso3.upper()
    row = (
        db.query(Synopsis)
        .filter(Synopsis.iso3 == iso3)
        .filter(Synopsis.approval_state.in_(_APPROVED_STATES))
        .order_by(Synopsis.generated_at.desc())
        .first()
    )
    if row is None:
        return None
    return SynopsisOut(
        id=row.id, iso3=row.iso3, text=row.text,
        key_points=row.key_points, generated_at=row.generated_at,
        approval_state=row.approval_state,
        approved_by=row.approved_by, approved_at=row.approved_at,
        prompt_trace_id=row.prompt_trace_id, tenant_id=row.tenant_id,
    )


@router.get("/api/admin/synopses")
def list_pending_synopses(
    db: DbSession,
    _user: CurrentUser,
) -> list[SynopsisListItem]:
    """List all proposed (pending) synopses for admin review."""
    rows = (
        db.query(Synopsis)
        .filter(Synopsis.approval_state == "proposed")
        .order_by(Synopsis.generated_at.desc())
        .limit(100)
        .all()
    )
    return [
        SynopsisListItem(
            id=r.id, iso3=r.iso3, text=r.text,
            generated_at=r.generated_at, approval_state=r.approval_state,
        )
        for r in rows
    ]


@router.post("/api/admin/synopses/{synopsis_id}/approve")
def approve_synopsis(
    synopsis_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SynopsisOut:
    """Approve a proposed synopsis."""
    row = db.query(Synopsis).filter(Synopsis.id == synopsis_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Synopsis not found")
    if row.approval_state != "proposed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve synopsis in state '{row.approval_state}'",
        )

    row.approval_state = "human_approved"
    row.approved_by = user.id
    row.approved_at = datetime.now(UTC)
    db.commit()

    return SynopsisOut(
        id=row.id, iso3=row.iso3, text=row.text,
        key_points=row.key_points, generated_at=row.generated_at,
        approval_state=row.approval_state,
        approved_by=row.approved_by, approved_at=row.approved_at,
        prompt_trace_id=row.prompt_trace_id, tenant_id=row.tenant_id,
    )


@router.post("/api/admin/synopses/{synopsis_id}/reject")
def reject_synopsis(
    synopsis_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SynopsisOut:
    """Reject a proposed synopsis."""
    row = db.query(Synopsis).filter(Synopsis.id == synopsis_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Synopsis not found")
    if row.approval_state != "proposed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject synopsis in state '{row.approval_state}'",
        )

    row.approval_state = "rejected"
    row.approved_by = user.id
    row.approved_at = datetime.now(UTC)
    db.commit()

    return SynopsisOut(
        id=row.id, iso3=row.iso3, text=row.text,
        key_points=row.key_points, generated_at=row.generated_at,
        approval_state=row.approval_state,
        approved_by=row.approved_by, approved_at=row.approved_at,
        prompt_trace_id=row.prompt_trace_id, tenant_id=row.tenant_id,
    )


@router.post("/api/admin/synopses/generate/{iso3}")
def trigger_synopsis_generation(
    iso3: str,
    db: DbSession,
    user: CurrentUser,
) -> SynopsisOut | dict[str, str]:
    """Admin trigger to generate a new synopsis for a country."""
    result = generate_synopsis(db, iso3, user_id=user.id)
    if result is None:
        return {"status": "skipped", "reason": "AI unavailable or no data"}
    return SynopsisOut(
        id=result.id, iso3=result.iso3, text=result.text,
        key_points=result.key_points, generated_at=result.generated_at,
        approval_state=result.approval_state,
        approved_by=result.approved_by, approved_at=result.approved_at,
        prompt_trace_id=result.prompt_trace_id, tenant_id=result.tenant_id,
    )
