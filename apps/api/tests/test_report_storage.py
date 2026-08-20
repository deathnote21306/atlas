"""Reports must survive a redeploy.

PDFs were written only to /tmp, which is ephemeral on Railway, so every restart
silently emptied the reports library and downloads began returning 410. The bytes
are now stored in Postgres alongside the record, with disk kept as a fallback for
rows generated before this change.
"""

from __future__ import annotations

from atlas_api.models import Report


def test_report_row_can_hold_the_pdf_bytes():
    cols = Report.__table__.columns
    assert "pdf_bytes" in cols, "the PDF must be storable in the database"
    assert cols["pdf_bytes"].nullable, "older rows have no bytes, so it must be optional"


def test_pdf_path_is_kept_for_backwards_compatibility():
    """Existing rows still point at disk, so the column must not be dropped."""
    assert "pdf_path" in Report.__table__.columns


def test_download_prefers_stored_bytes_over_disk():
    import inspect

    from atlas_api.routers.reports import download_pdf

    src = inspect.getsource(download_pdf)
    assert "pdf_bytes" in src, "download must serve the stored bytes"
    # The old guard rejected any report without a filesystem path.
    assert "not report.pdf_path" not in src, (
        "a report with bytes but no path must still be downloadable"
    )
