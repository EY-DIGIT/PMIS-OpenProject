"""
FastAPI main application for OpenProject User Service.

This FastAPI backend is compatible with the OpenProject Angular frontend
and implements the OpenProject API v3 user endpoints.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging

from .database import init_db
from .api import users, auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the application"""
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")
    yield
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="OpenProject User Service API",
    description="""
    FastAPI implementation of OpenProject User Service compatible with OpenProject API v3.

    ## Authentication

    This API supports multiple authentication methods:

    1. **API Key (Basic Auth)**: Use username='apikey' and your API key as password
    2. **Bearer Token**: Use OAuth2 or JWT tokens
    3. **Session-based**: For Angular client, use X-Requested-With header

    ## Features

    - Complete user CRUD operations
    - User authentication and session management
    - Password management
    - User locking/unlocking
    - HAL+JSON response format

    ## Compatibility

    This backend is designed to be compatible with the OpenProject Angular frontend.
    It implements the OpenProject API v3 conventions and HAL+JSON format.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware for Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",  # Angular dev server
        "http://localhost:3000",
        "http://localhost:8080",
        "*"  # In production, specify exact origins
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    errors = {}
    for error in exc.errors():
        field = error['loc'][-1] if error['loc'] else 'unknown'
        message = error['msg']
        if field not in errors:
            errors[field] = []
        errors[field].append(message)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "_type": "Error",
            "errorIdentifier": "urn:openproject-org:api:v3:errors:PropertyConstraintViolation",
            "message": "Validation failed",
            "details": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "_type": "Error",
            "errorIdentifier": "urn:openproject-org:api:v3:errors:InternalServerError",
            "message": "Internal server error"
        }
    )


# Include routers
app.include_router(users.router)
app.include_router(auth.router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "_type": "Root",
        "instanceName": "OpenProject User Service",
        "_links": {
            "self": {"href": "/"},
            "users": {"href": "/api/v3/users"},
            "user": {"href": "/api/v3/users/{id}"},
            "docs": {"href": "/api/docs"}
        }
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "OpenProject User Service",
        "version": "1.0.0"
    }


# API v3 root
@app.get("/api/v3")
async def api_v3_root():
    """API v3 root endpoint"""
    return {
        "_type": "Root",
        "_links": {
            "self": {"href": "/api/v3"},
            "users": {"href": "/api/v3/users"},
            "configuration": {"href": "/api/v3/configuration"}
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "user_service.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
