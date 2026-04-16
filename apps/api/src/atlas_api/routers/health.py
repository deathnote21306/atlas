from atlas_schemas.health import HealthResponse
from fastapi import APIRouter

from atlas_api import __version__

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
