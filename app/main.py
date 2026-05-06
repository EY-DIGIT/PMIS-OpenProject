"""
Main application entry point.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional
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
# Run in reverse order of how added, Auth -> Logging
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


# ---------------------------------------------------------------------------
# Doc 35: local fallback file route.
#
# Comment rows now store an attachment URL directly. When the deployment
# hasn't configured FILE_SERVER_PUBLIC_BASE_URL (typical for dev), the
# stored URL is a relative storage_key and the FE expects the BE to
# serve the bytes itself. This route provides exactly that fallback.
# Disabled by setting FILE_SERVER_LOCAL_FALLBACK_ENABLED=False once a
# real external file server is reachable from the FE directly.
# ---------------------------------------------------------------------------
if settings.FILE_SERVER_LOCAL_FALLBACK_ENABLED:
    from urllib.parse import quote
    from fastapi import HTTPException
    from fastapi.responses import StreamingResponse

    from app.infrastructure.storage import (
        StorageUnavailableError,
        get_storage,
    )

    @app.get("/files/{storage_key:path}", include_in_schema=False, tags=["files"])
    def serve_local_file(storage_key: str):
        """Stream bytes for an attachment stored on the local FileStorage.

        ``storage_key`` is the relative path the storage layer assigned
        when the file was uploaded (e.g. ``attachments/2026/05/abc.pdf``).
        Path-escape attempts are blocked inside ``FileStorage.absolute_path``.

        Auth-free by design — the URLs are unguessable (UUID-prefixed)
        and this route exists only for the dev-fallback scenario where
        an external file server isn't deployed. Production deployments
        either set FILE_SERVER_PUBLIC_BASE_URL to a real CDN / file
        server (FE fetches there directly, this route is unused) or
        flip FILE_SERVER_LOCAL_FALLBACK_ENABLED=False (route gone).
        """
        storage = get_storage()
        try:
            stream = storage.open(storage_key)
        except StorageUnavailableError:
            raise HTTPException(status_code=404, detail="File not found.")

        # Reuse the original filename from the trailing path component
        # so the browser's Save-As dialog shows something readable.
        suggested_name = storage_key.rsplit("/", 1)[-1]
        # storage_key embeds a UUID prefix like "{uuid}_{name}"; strip
        # the UUID for display.
        if "_" in suggested_name:
            suggested_name = suggested_name.split("_", 1)[1] or suggested_name

        def chunk_iter():
            try:
                while True:
                    chunk = stream.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk
            finally:
                stream.close()

        safe = quote(suggested_name)
        return StreamingResponse(
            chunk_iter(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": (
                    f'inline; filename="{suggested_name}"; '
                    f"filename*=UTF-8''{safe}"
                ),
            },
        )

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

    Reports the status of subsystems the app depends on. Currently:
      - the API process itself ("status")
      - file-storage backend reachability (NFS mount in prod, local
        folder in dev) — surfaced separately so ops can distinguish a
        fully-healthy app from one that's serving but can't accept
        attachment uploads.
      - notification client config + reachability — diagnostic for the
        2FA / forgot-password flow. Exposes which backend is selected
        (``mock`` or ``http``), the configured service URL, and a quick
        reachability probe so ops can tell at a glance whether the BE
        will actually dispatch OTP emails or silently sink them in
        the audit table.

    The NFS server / export are reported back from settings (informational
    — the app doesn't connect to them directly; the OS mount does). They
    let ops verify which file store this instance is wired to.
    """
    from .infrastructure.storage import get_storage

    storage_healthy = False
    try:
        storage_healthy = get_storage().is_healthy()
    except Exception:  # noqa: BLE001
        storage_healthy = False

    # Notification subsystem diagnostic. NEVER raises — health must
    # always return 200 even if the notif service is down (otherwise
    # k8s liveness probes would flap).
    notif_backend = (settings.NOTIFICATION_CLIENT or "mock").lower()
    notif_url = settings.NOTIFICATION_SERVICE_URL or ""
    notif_reachable: bool = False
    notif_reach_error: Optional[str] = None
    if notif_backend == "http" and notif_url:
        try:
            import httpx
            with httpx.Client(timeout=httpx.Timeout(connect=2.0, read=3.0, write=3.0, pool=3.0)) as c:
                r = c.get(f"{notif_url.rstrip('/')}/api/v1/health")
            notif_reachable = (200 <= r.status_code < 300)
            if not notif_reachable:
                notif_reach_error = f"http {r.status_code}"
        except Exception as e:  # noqa: BLE001
            notif_reach_error = f"{type(e).__name__}: {e}"

    return {
        "_type": "Health",
        "status": "healthy",
        "version": settings.APP_VERSION,
        "storage": {
            "healthy": storage_healthy,
            "base_path": settings.ATTACHMENTS_STORAGE_BASE_PATH,
            "nfs_server": settings.ATTACHMENTS_NFS_SERVER or None,
            "nfs_export": settings.ATTACHMENTS_NFS_EXPORT or None,
            "max_bytes": settings.ATTACHMENTS_MAX_BYTES,
        },
        "notification": {
            # Which backend the factory selects on every dispatch.
            # ``mock`` writes to notification_log only (no real email);
            # ``http`` POSTs to NOTIFICATION_SERVICE_URL. If this is
            # ``mock`` in a deployed env, OTP / reset emails never go
            # out — set NOTIFICATION_CLIENT=http to fix.
            "backend": notif_backend,
            "service_url": notif_url or None,
            # Live probe (only attempted when backend=http + url set).
            # ``true`` means the BE process can reach the notif service
            # right now. ``false`` with an error message means the
            # network path is broken — fix that before the next OTP
            # request.
            "reachable": notif_reachable,
            "reach_error": notif_reach_error,
        },
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
