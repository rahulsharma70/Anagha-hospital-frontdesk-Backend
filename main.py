import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.database import init_db
from core.limiter import init_redis
from fastapi_limiter import FastAPILimiter

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routers once they are refactored
from routers import users, hospitals, appointments, operations, payments, admin, cities, whatsapp_logs

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Unified Hospital API Server...")
    init_db()
    # Initialize Redis for rate limiting
    redis_conn = await init_redis()
    if redis_conn:
        await FastAPILimiter.init(redis_conn)
        logger.info("✅ Rate limiter initialized.")
    else:
        logger.warning("⚠️ Rate limiting will be disabled (Redis unavailable).")
    yield
    # Shutdown
    logger.info("🛑 Shutting down Server...")

app = FastAPI(
    title="Hospital Booking System API",
    description="Unified API for Web and Mobile Hospital Booking",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "https://anaghahealthconnect.com",
        "https://www.anaghahealthconnect.com",
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(users.router)
app.include_router(hospitals.router)
app.include_router(appointments.router)
app.include_router(operations.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(whatsapp_logs.router)

# Validation exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    error_details = [{"field": ".".join(str(loc) for loc in e["loc"]), "message": e["msg"]} for e in errors]
    return JSONResponse(
        status_code=422,
        content={"detail": error_details, "message": "Validation error"}
    )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global Error handling {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "message": str(exc) if settings.ENVIRONMENT != "production" else "An unexpected error occurred."}
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=(settings.ENVIRONMENT=="development"))
