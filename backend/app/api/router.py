from fastapi import APIRouter
from app.api.v1.endpoints import (
    alerts,
    audit,
    auth,
    health,
    incidents,
    integrations,
    jobs,
    logs,
)

api_router = APIRouter()

# Include routes under the API router
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(logs.router, tags=["Logs"])
api_router.include_router(incidents.router, tags=["Incidents"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
