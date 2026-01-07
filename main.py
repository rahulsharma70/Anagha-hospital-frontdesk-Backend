"""
Main entry point for the FastAPI application
Used for deployment on Render and other platforms
"""

# Import the FastAPI app from server_web
from server_web import app

# This allows Render to use: uvicorn backend.main:app
# Or: python -m uvicorn backend.main:app
__all__ = ["app"]

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

