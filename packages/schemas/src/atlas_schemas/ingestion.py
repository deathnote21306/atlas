from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DataVintage(BaseModel):
    id: UUID
    created_at: datetime
    source: str
    notes: str | None = None


class SourceStats(BaseModel):
    source: str
    rows_written: int
    rows_skipped: int
    errors: list[str]
    duration_seconds: float


class IngestionReport(BaseModel):
    vintage_id: UUID
    started_at: datetime
    finished_at: datetime
    sources: list[SourceStats]
    ok: bool
