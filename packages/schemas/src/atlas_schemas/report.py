from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReportOut(BaseModel):
    id: uuid.UUID
    template: str
    iso3: str
    generated_at: datetime
    generated_by: uuid.UUID | None
    status: str  # pending | ready | failed
    manifest: dict[str, Any] | None

    model_config = {"from_attributes": True}


class GenerateReportRequest(BaseModel):
    iso3: str
    template: str = "country_brief"
