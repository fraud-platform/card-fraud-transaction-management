"""API routes package."""

from fastapi import APIRouter

from app.api.routes.bulk import router as bulk_router
from app.api.routes.cases import router as cases_router
from app.api.routes.decision_events import router as decision_events_router
from app.api.routes.notes import router as notes_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.worklist import router as worklist_router

# Create API router with all sub-routers
api_router = APIRouter()

# Register all route modules
api_router.include_router(decision_events_router)
api_router.include_router(reviews_router)
api_router.include_router(notes_router)
api_router.include_router(cases_router)
api_router.include_router(worklist_router)
api_router.include_router(bulk_router)


__all__ = [
    "api_router",
    "decision_events_router",
    "reviews_router",
    "notes_router",
    "cases_router",
    "worklist_router",
    "bulk_router",
]
