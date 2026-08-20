"""Reports API endpoints — generate, list, and download country brief PDFs."""

from __future__ import annotations

import uuid
from pathlib import Path

from atlas_schemas.report import GenerateReportRequest, ReportOut
from fastapi import APIRouter, HTTPException, Response, status

from atlas_api.deps import CurrentUser, DbSession, _check_iso3
from atlas_api.services.reporting.service import generate_country_brief, get_report, list_reports

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def post_generate(
    body: GenerateReportRequest,
    session: DbSession,
    user: CurrentUser,
) -> ReportOut:
    """Generate a new country brief PDF report."""
    iso3 = _check_iso3(body.iso3)
    try:
        report = generate_country_brief(session, iso3, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ReportOut.model_validate(report)


@router.get("", response_model=list[ReportOut])
def list_all(
    session: DbSession,
    _: CurrentUser,
    iso3: str | None = None,
) -> list[ReportOut]:
    """List generated reports, optionally filtered by country."""
    if iso3:
        iso3 = _check_iso3(iso3)
    return [ReportOut.model_validate(r) for r in list_reports(session, iso3)]


@router.get("/{report_id}", response_model=ReportOut)
def get_one(
    report_id: uuid.UUID,
    session: DbSession,
    _: CurrentUser,
) -> ReportOut:
    """Get report metadata by ID."""
    report = get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    return ReportOut.model_validate(report)


@router.get("/{report_id}/download")
def download_pdf(
    report_id: uuid.UUID,
    session: DbSession,
    _: CurrentUser,
) -> Response:
    """Download the generated PDF."""
    report = get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")
    if report.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"PDF not available — report status is '{report.status}'",
        )

    # Stored bytes first: they survive restarts. Disk is only a fallback for rows
    # generated before PDFs were kept in the database.
    content = report.pdf_bytes
    if not content and report.pdf_path:
        pdf_path = Path(report.pdf_path)
        if pdf_path.exists():
            content = pdf_path.read_bytes()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "This report was generated before reports were stored durably. "
                "Generate it again."
            ),
        )

    filename = f"atlas_{report.iso3}_{report.generated_at.strftime('%Y%m%d')}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
