from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies.auth import get_current_user
from app.integrations import (
    get_all_integrations_status,
    get_deployment_provider,
    get_infrastructure_provider,
    get_metrics_provider,
    get_source_control_provider,
)
from app.models.user import User

router = APIRouter()


@router.get("/status")
def get_integrations_status(
    current_user: User = Depends(get_current_user),
):
    """
    Return connection status of all external integration providers.
    Explicitly reports CONNECTED, NOT_CONNECTED, UNAVAILABLE, or ERROR.
    Never fabricates fake connected states.
    """
    return get_all_integrations_status()


@router.get("/deployment/recent")
def get_recent_deployments(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Fetch recent deployment workflow runs from the configured deployment provider."""
    provider = get_deployment_provider()
    return provider.get_recent_deployments(limit=limit)


@router.get("/source-control/commits")
def get_recent_commits(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Fetch recent commits from configured source control provider (Read-Only)."""
    provider = get_source_control_provider()
    return provider.get_recent_commits(limit=limit)


@router.get("/source-control/pull-requests")
def get_pull_requests(
    state: str = Query("open", pattern="^(open|closed|all)$"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Fetch pull requests from configured source control provider (Read-Only)."""
    provider = get_source_control_provider()
    return provider.get_pull_requests(state=state, limit=limit)


@router.get("/infrastructure/status")
def get_infrastructure_status(
    service_name: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Fetch infrastructure service health from configured infrastructure provider."""
    provider = get_infrastructure_provider()
    return provider.get_service_status(service_name=service_name)


@router.get("/metrics/query")
def query_metrics(
    query: str = Query(..., description="PromQL expression"),
    start_time: Optional[float] = Query(None),
    end_time: Optional[float] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Query time-series telemetry from configured metrics provider (e.g. Prometheus)."""
    provider = get_metrics_provider()
    return provider.query_metric(query=query, start_time=start_time, end_time=end_time)
