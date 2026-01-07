"""
Message Logger Service
Logs all WhatsApp messages sent for audit and tracking
"""
import logging
import json
import os
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Directory for message logs
LOG_DIR = "./whatsapp_logs"

def ensure_log_directory():
    """Ensure log directory exists."""
    os.makedirs(LOG_DIR, exist_ok=True)


def log_message(
    hospital_id: int,
    mobile: str,
    message: str,
    status: str,
    error: Optional[str] = None,
    retry_count: int = 0
):
    """
    Log WhatsApp message attempt.
    
    Args:
        hospital_id: Hospital ID
        mobile: Mobile number
        message: Message text
        status: 'success' or 'failed'
        error: Error message if failed
        retry_count: Number of retry attempts
    """
    try:
        ensure_log_directory()
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "hospital_id": hospital_id,
            "mobile": mobile,
            "message": message[:200],  # Truncate long messages
            "status": status,
            "error": error,
            "retry_count": retry_count
        }
        
        # Log to file (one file per hospital per day)
        log_date = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = f"{LOG_DIR}/hospital_{hospital_id}_{log_date}.jsonl"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        # Also log to application logger
        if status == "success":
            logger.info(f"Message logged: {mobile} - {status}")
        else:
            logger.warning(f"Message logged: {mobile} - {status} - {error}")
            
    except Exception as e:
        logger.error(f"Error logging message: {str(e)}")


def get_message_logs(
    hospital_id: int,
    date: Optional[str] = None,
    status: Optional[str] = None
) -> List[Dict]:
    """
    Get message logs for a hospital.
    
    Args:
        hospital_id: Hospital ID
        date: Date in YYYY-MM-DD format (optional)
        status: Filter by status ('success' or 'failed') (optional)
    
    Returns:
        List of log entries
    """
    try:
        ensure_log_directory()
        
        if date:
            log_file = f"{LOG_DIR}/hospital_{hospital_id}_{date}.jsonl"
        else:
            # Get today's log file
            log_date = datetime.utcnow().strftime("%Y-%m-%d")
            log_file = f"{LOG_DIR}/hospital_{hospital_id}_{log_date}.jsonl"
        
        if not os.path.exists(log_file):
            return []
        
        logs = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if not status or entry.get("status") == status:
                        logs.append(entry)
        
        return logs
        
    except Exception as e:
        logger.error(f"Error reading message logs: {str(e)}")
        return []



