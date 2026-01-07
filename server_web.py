"""
FastAPI Web Server (Port 3000)
Serves web frontend (templates, static) and API endpoints
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Add backend directory to path
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

# Load environment variables
env_path = BACKEND_DIR / ".env"
parent_env_path = BACKEND_DIR.parent / ".env"

if parent_env_path.exists():
    load_dotenv(parent_env_path, override=True)
elif env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

# Override config module before other imports
import config_web
sys.modules['config'] = config_web
import config

# Import error monitoring and audit logging
# Note: Sentry initializes automatically when error_monitoring module is imported
from services.error_monitoring import capture_exception, log_error_with_context
from services.audit_logger import log_login_attempt

# Import database initialization
from database import init_db, get_supabase

# Import routers
from routers import users, hospitals, appointments, operations, payments, admin, whatsapp_logs

# Import scheduler service
from services.scheduler_service import start_scheduler, shutdown_scheduler

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Web Server...")
    init_db()
    start_scheduler()
    yield
    # Shutdown
    print("🛑 Shutting down Web Server...")
    shutdown_scheduler()

# Create FastAPI app
app = FastAPI(
    title="Hospital Booking System - Web API",
    description="Web interface and API for Hospital Booking System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Frontend is served separately on port 5173 (Vite dev server)
# This server only handles API requests

# Include routers
app.include_router(users.router)
app.include_router(hospitals.router)
app.include_router(appointments.router)
app.include_router(operations.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(whatsapp_logs.router)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with error logging"""
    log_error_with_context(exc, request)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Error has been logged."}
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        supabase = get_supabase()
        if supabase:
            # Test database connection
            supabase.table("hospitals").select("id").limit(1).execute()
            return {
                "status": "healthy",
                "database": "connected",
                "service": "web"
            }
        else:
            return {
                "status": "healthy",
                "database": "not_configured",
                "service": "web"
            }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "error",
                "error": str(e),
                "service": "web"
            }
        )

# Note: React frontend is served separately on port 5173 (Vite dev server)
# This server only handles API requests
# For production, you may want to serve static files from a reverse proxy (nginx) or CDN

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server_web:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=True
    )