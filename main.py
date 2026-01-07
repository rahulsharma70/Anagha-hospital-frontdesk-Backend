"""
Main entry point for the FastAPI application
Used for deployment on Render and other platforms
"""

import os
import sys
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Import the FastAPI app from server_web
from server_web import app
from database import get_supabase

# This allows Render to use: uvicorn backend.main:app
# Or: python -m uvicorn backend.main:app
__all__ = ["app"]

# Additional routes for deployment and monitoring

@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Hospital Booking System API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint"""
    try:
        supabase = get_supabase()
        db_status = "disconnected"
        
        if supabase:
            try:
                # Test database connection
                supabase.table("hospitals").select("id").limit(1).execute()
                db_status = "connected"
            except Exception as db_error:
                db_status = f"error: {str(db_error)}"
        else:
            db_status = "not_configured"
        
        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "database": db_status,
            "service": "web",
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "production")
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint - checks if service is ready to accept traffic"""
    try:
        supabase = get_supabase()
        if not supabase:
            return JSONResponse(
                status_code=503,
                content={
                    "ready": False,
                    "reason": "Database not configured",
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        # Test database connection
        supabase.table("hospitals").select("id").limit(1).execute()
        
        return {
            "ready": True,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "reason": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/live")
async def liveness_check():
    """Liveness check endpoint - checks if service is alive"""
    return {
        "alive": True,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/info")
async def system_info():
    """System information endpoint"""
    try:
        supabase = get_supabase()
        db_info = {
            "configured": supabase is not None,
            "status": "connected" if supabase else "not_configured"
        }
        
        if supabase:
            try:
                # Get database stats
                hospitals_result = supabase.table("hospitals").select("id", count="exact").execute()
                users_result = supabase.table("users").select("id", count="exact").execute()
                
                db_info["stats"] = {
                    "hospitals": hospitals_result.count if hasattr(hospitals_result, 'count') else "unknown",
                    "users": users_result.count if hasattr(users_result, 'count') else "unknown"
                }
            except Exception:
                db_info["stats"] = "unavailable"
        
        return {
            "service": "Hospital Booking System API",
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "production"),
            "database": db_info,
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version.split()[0] if sys.version else "unknown"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/status")
async def status_check():
    """Status endpoint with detailed system status"""
    try:
        supabase = get_supabase()
        
        status = {
            "service": "web",
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Check database
        if supabase:
            try:
                supabase.table("hospitals").select("id").limit(1).execute()
                status["components"]["database"] = {
                    "status": "operational",
                    "message": "Connected"
                }
            except Exception as e:
                status["components"]["database"] = {
                    "status": "degraded",
                    "message": str(e)
                }
                status["status"] = "degraded"
        else:
            status["components"]["database"] = {
                "status": "not_configured",
                "message": "Database not configured"
            }
        
        return status
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "service": "web",
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

if __name__ == "__main__":
    import uvicorn
    import os
    from config import SERVER_HOST, SERVER_PORT
    
    # Get port from environment (Render sets PORT env var)
    port = int(os.getenv("PORT", SERVER_PORT))
    host = os.getenv("HOST", SERVER_HOST)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False  # Disable reload in production
    )

