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
from .core.response import format_error_response, api_response
from .core.middleware import AuthenticationMiddleware, LoggingMiddleware
from .infrastructure.db.session import init_db
from .api import api_v3_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__) # Logging for main

# Replacement for @app.on_event("startup") and @app.on_event("shutdown")
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
    title=settings.APP_NAME, # from .core.config
    version=settings.APP_VERSION, # from .core.config
    description="OpenProject-compatible User Management API",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True}
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
# Handles all DomainError or subclass exceptions as defined in .core.errors
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

    error_payload = format_error_response(
        error_type=exc.__class__.__name__,
        message=exc.message,
        details=exc.details
    )

    return api_response(
        data=None,
        error=error_payload,
        message=None,
        status=status_code
    )


@app.exception_handler(Exception)
# Handles all errors besides DomainError or subclass exceptions as defined in .core.errors
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

    error_payload = format_error_response(
        error_type="InternalError",
        message="An internal error occurred. Please try again later.",
        details={"error": str(exc)} if settings.DEBUG else None
    )

    return api_response(
        data=None,
        error=error_payload,
        message=None,
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


# Include routers
app.include_router(api_v3_router)

# OpenAPI security scheme configuration
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    """
    Customize OpenAPI schema to include Bearer token authentication.

    This ensures the Swagger UI shows the authentication token requirement
    for all protected endpoints.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="OpenProject-compatible Project Management API with JWT Authentication",
        routes=app.routes,
    )

    # Add security scheme for Bearer token
    openapi_schema["components"]["securitySchemes"] = {
        "bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer token. Obtain token via /api/v3/users/login"
        }
    }

    # Apply bearer auth to all paths except public endpoints
    public_paths = ["/health", "/", "/api/v3/users/login", "/api/v3/users/introspect"]

    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "patch", "delete", "options", "head", "trace"]:
                # Add security requirement for non-public endpoints
                if path not in public_paths:
                    if "security" not in operation:
                        operation["security"] = [{"bearer": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

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
