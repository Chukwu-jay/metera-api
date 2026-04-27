from fastapi import APIRouter

from app.observability.metrics import snapshot_metrics

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def summary() -> dict:
    return snapshot_metrics()
