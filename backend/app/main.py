from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uuid
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.api.v1.endpoints.health import router as health_router
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
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG else None,
        docs_url=f"{settings.API_V1_PREFIX}/docs" if settings.DEBUG else None,
        redoc_url=f"{settings.API_V1_PREFIX}/redoc" if settings.DEBUG else None,
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
    # API Routers
    # --------------------------------------------------------------------------
    # Expose /health at root level for load balancers / simple health checks
    app.include_router(health_router, tags=["Health"])

    # Expose versioned API routes under API_V1_PREFIX (e.g., /api/v1/health)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
