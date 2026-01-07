"""
Error Monitoring and Logging
Provides centralized error tracking and logging (Sentry optional)
"""
import logging
from typing import Optional
from functools import wraps
from fastapi import Request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def capture_exception(error: Exception, context: Optional[dict] = None):
    """Capture exception and log it"""
    error_msg = f"Unhandled exception: {error}"
    if context:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        error_msg += f" | Context: {context_str}"
    logger.error(error_msg, exc_info=True)


def capture_message(message: str, level: str = "info", context: Optional[dict] = None):
    """Capture message and log it"""
    log_msg = message
    if context:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        log_msg += f" | Context: {context_str}"
    logger.log(logging.INFO if level == "info" else logging.WARNING, log_msg)


def log_error_with_context(error: Exception, request: Optional[Request] = None, user_id: Optional[int] = None):
    """Log error with request context"""
    context = {}
    
    if request:
        context["request"] = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client": request.client.host if request.client else None,
        }
        # Add headers (excluding sensitive ones)
        if hasattr(request, "headers"):
            headers = dict(request.headers)
            # Remove sensitive headers
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                headers.pop(header.lower(), None)
            context["headers"] = headers
    
    if user_id:
        context["user_id"] = user_id
    
    capture_exception(error, context)


def error_handler(func):
    """Decorator for error handling with Sentry"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Extract request if available
            request = None
            user_id = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # Try to get user_id from kwargs
            current_user = kwargs.get("current_user")
            if current_user and isinstance(current_user, dict):
                user_id = current_user.get("id")
            
            log_error_with_context(e, request, user_id)
            raise
    
    return wrapper

