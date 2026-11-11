import os
import sys
from pathlib import Path

# Ensure backend root directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
import uuid
from fastapi import FastAPI, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.v1.endpoints.health import HealthResponse, router as health_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

# Initialize logging
setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager handling application startup and shutdown events."""
    logger.info(
        "Starting %s v%s [Environment: %s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Application factory creating the configured FastAPI instance."""
    # Determine documentation URLs based on configuration
    docs_enabled = bool(settings.ENABLE_DOCS)
    openapi_url = settings.OPENAPI_URL if (docs_enabled and settings.OPENAPI_URL) else None
    docs_url = settings.DOCS_URL if (docs_enabled and settings.DOCS_URL) else None
    redoc_url = settings.REDOC_URL if (docs_enabled and settings.REDOC_URL) else None

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url=openapi_url,
        docs_url=docs_url,
        redoc_url=redoc_url,
        lifespan=lifespan,
    )

    # --------------------------------------------------------------------------
    # Request ID and Observability Middleware
    # --------------------------------------------------------------------------
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --------------------------------------------------------------------------
    # Global Exception Handlers
    # --------------------------------------------------------------------------
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
        logger.warning(
            "HTTP error %s on %s %s [req_id=%s]: %s",
            exc.status_code,
            request.method,
            request.url.path,
            req_id,
            exc.detail,
        )

        if isinstance(exc.detail, dict) and "error" in exc.detail:
            error_data = dict(exc.detail["error"])
            if "request_id" not in error_data:
                error_data["request_id"] = req_id
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail, "error": error_data},
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error": {
                    "code": exc.status_code,
                    "message": str(exc.detail),
                    "request_id": req_id,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
        logger.warning(
            "Validation error on %s %s [req_id=%s]: %s",
            request.method,
            request.url.path,
            req_id,
            str(exc.errors()),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Validation Error",
                    "details": jsonable_encoder(exc.errors()),
                    "request_id": req_id,
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
        logger.error(
            "Unhandled server error on %s %s [req_id=%s]: %s",
            request.method,
            request.url.path,
            req_id,
            str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred.",
                    "request_id": req_id,
                }
            },
        )

    # --------------------------------------------------------------------------
    # Root & Utility Endpoints
    # --------------------------------------------------------------------------
    @app.get(
        "/",
        response_model=HealthResponse,
        tags=["Root"],
        summary="Application Root",
        description="Root status and metadata endpoint returning application name, status, and version without sensitive data.",
    )
    def root() -> HealthResponse:
        return HealthResponse(
            status="ok",
            app_name=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.APP_ENV,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.get(
        "/favicon.ico",
        include_in_schema=False,
        summary="Favicon",
        description="Returns 204 No Content for favicon requests to prevent unnecessary 404 logs.",
    )
    def favicon() -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # --------------------------------------------------------------------------
    # Backward Compatibility Redirects for Legacy Prefixed Documentation Routes
    # --------------------------------------------------------------------------
    if docs_enabled:
        if docs_url and docs_url != f"{settings.API_V1_PREFIX}/docs":
            @app.get(f"{settings.API_V1_PREFIX}/docs", include_in_schema=False)
            def legacy_docs_redirect():
                return RedirectResponse(url=docs_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

        if redoc_url and redoc_url != f"{settings.API_V1_PREFIX}/redoc":
            @app.get(f"{settings.API_V1_PREFIX}/redoc", include_in_schema=False)
            def legacy_redoc_redirect():
                return RedirectResponse(url=redoc_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

        if openapi_url and openapi_url != f"{settings.API_V1_PREFIX}/openapi.json":
            @app.get(f"{settings.API_V1_PREFIX}/openapi.json", include_in_schema=False)
            def legacy_openapi_redirect():
                return RedirectResponse(url=openapi_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # --------------------------------------------------------------------------
    # API Routers
    # --------------------------------------------------------------------------
    # Expose /health at root level for load balancers / simple health checks
    app.include_router(health_router, tags=["Health"])

    # Expose versioned API routes under API_V1_PREFIX (e.g., /api/v1/health)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", settings.PORT))
    host = os.environ.get("HOST", settings.HOST)
    logger.info("Starting %s via CLI on %s:%d", settings.APP_NAME, host, port)
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
