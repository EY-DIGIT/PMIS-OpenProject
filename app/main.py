"""
Main application entry point.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.errors import DomainError, get_http_status
from .core.response import format_error_response
from .core.middleware import AuthenticationMiddleware, LoggingMiddleware
from .infrastructure.db.session import init_db
from .api import api_v3_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")
    logger.info(f"Application {settings.APP_NAME} v{settings.APP_VERSION} started")

    yield

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="OpenProject-compatible User Management API",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthenticationMiddleware)


# Exception handlers
@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    """
    Handle domain errors.

    Args:
        request: FastAPI request
        exc: Domain error exception

    Returns:
        JSON response with error details
    """
    status_code = get_http_status(exc)

    response = format_error_response(
        error_type=exc.__class__.__name__,
        message=exc.message,
        details=exc.details
    )

    return JSONResponse(
        status_code=status_code,
        content=response
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle general exceptions.

    Args:
        request: FastAPI request
        exc: Exception

    Returns:
        JSON response with error details
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    response = format_error_response(
        error_type="InternalError",
        message="An internal error occurred. Please try again later.",
        details={"error": str(exc)} if settings.DEBUG else None
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response
    )


# Include routers
app.include_router(api_v3_router)


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status
    """
    return {
        "_type": "Health",
        "status": "healthy",
        "version": settings.APP_VERSION
    }


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint.

    Returns:
        API information
    """
    return {
        "_type": "Root",
        "_links": {
            "self": {"href": "/"},
            "users": {"href": "/api/v3/users"}
        },
        "instanceName": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
