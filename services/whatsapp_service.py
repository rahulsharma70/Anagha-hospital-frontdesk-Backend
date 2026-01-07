"""
WhatsApp Web Automation Service using Selenium
Handles sending WhatsApp messages from hospital's WhatsApp number
"""
import os
import time
import urllib.parse
import logging
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from services.message_logger import log_message

logger = logging.getLogger(__name__)

# Store active driver sessions per hospital
_driver_sessions = {}

def open_whatsapp_session(hospital_id: int) -> Optional[webdriver.Chrome]:
    """
    Open WhatsApp Web session for a hospital (One Time).
    Hospital admin scans QR once only. Session remains logged in.
    
    Requirements:
    - WhatsApp Web opened once
    - QR scanned manually
    - Chrome session saved
    - No logout unless session expires
    
    Args:
        hospital_id: Hospital ID for session management
    
    Returns:
        webdriver.Chrome: Chrome driver instance, or None if failed
    """
    # Check if session already exists and is active
    if hospital_id in _driver_sessions:
        driver = _driver_sessions[hospital_id]
        try:
            # Check if driver is still active
            driver.current_url
            logger.info(f"Using existing WhatsApp session for hospital {hospital_id}")
            return driver
        except Exception:
            # Session expired, remove it
            del _driver_sessions[hospital_id]
    
    # Create new session
    try:
        # Create directory for hospital's WhatsApp session data
        session_dir = f"./whatsapp_sessions/{hospital_id}"
        os.makedirs(session_dir, exist_ok=True)
        
        # Chrome options with user data directory (persistent session)
        options = Options()
        options.add_argument(f"--user-data-dir={os.path.abspath(session_dir)}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Create Chrome driver
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        
        # Navigate to WhatsApp Web
        driver.get("https://web.whatsapp.com")
        
        logger.info(f"WhatsApp Web opened for hospital {hospital_id}")
        logger.info("Hospital admin scans QR once only. Session remains logged in.")
        
        # Wait for QR code scan (first time only)
        # Wait up to 2 minutes for user to scan QR code
        try:
            WebDriverWait(driver, 120).until(
                lambda d: "web.whatsapp.com" in d.current_url and "qr" not in d.current_url.lower()
            )
            logger.info(f"WhatsApp Web session established for hospital {hospital_id}")
        except TimeoutException:
            logger.warning(f"QR code scan timeout for hospital {hospital_id}")
            logger.info("Session will be saved. You can scan QR code later.")
            # Don't quit - let user scan QR code later
        
        # Store session (persistent - no logout unless session expires)
        _driver_sessions[hospital_id] = driver
        return driver
        
    except Exception as e:
        logger.error(f"Error opening WhatsApp session for hospital {hospital_id}: {str(e)}")
        return None


def get_whatsapp_driver(hospital_id: int) -> Optional[webdriver.Chrome]:
    """
    Get or create WhatsApp Web driver session for a hospital.
    Uses open_whatsapp_session() internally.
    """
    return open_whatsapp_session(hospital_id)


def send_whatsapp_message(
    driver: webdriver.Chrome,
    mobile: str,
    message: str,
    hospital_id: Optional[int] = None,
    retry_count: int = 0,
    max_retries: int = 3
) -> bool:
    """
    Send WhatsApp message using driver.
    
    Trigger this after booking + CSV save.
    
    Features:
    - Retry failed messages (up to max_retries)
    - Logs all message attempts
    - Error handling & logging
    
    Args:
        driver: Chrome WebDriver instance (from open_whatsapp_session)
        mobile: Mobile number (with +91 prefix)
        message: Message text to send
        hospital_id: Hospital ID for logging (optional)
        retry_count: Current retry attempt (internal use)
        max_retries: Maximum number of retry attempts
    
    Returns:
        bool: True if message sent successfully, False otherwise
    """
    try:
        # Encode message for URL
        text = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com/send?phone={mobile}&text={text}"
        
        # Navigate to chat
        driver.get(url)
        
        # Wait for page to load
        time.sleep(10)
        
        # Find and click send button
        send_btn = driver.find_element(By.XPATH, "//span[@data-icon='send']")
        send_btn.click()
        
        # Log successful message
        if hospital_id:
            log_message(hospital_id, mobile, message, "success", retry_count=retry_count)
        
        logger.info(f"Message sent successfully to {mobile}")
        return True
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error sending WhatsApp message: {error_msg}")
        
        # Log failed message
        if hospital_id:
            log_message(hospital_id, mobile, message, "failed", error=error_msg, retry_count=retry_count)
        
        # Retry if not exceeded max retries
        if retry_count < max_retries:
            logger.info(f"Retrying message to {mobile} (attempt {retry_count + 1}/{max_retries})")
            time.sleep(5)  # Wait before retry
            return send_whatsapp_message(driver, mobile, message, hospital_id, retry_count + 1, max_retries)
        
        return False


def send_whatsapp_message_by_hospital_id(
    hospital_id: int,
    mobile: str,
    message: str
) -> bool:
    """
    Send WhatsApp message by hospital ID (wrapper function).
    Gets driver and calls send_whatsapp_message().
    
    Args:
        hospital_id: Hospital ID for session management
        mobile: Mobile number (with or without +91 prefix)
        message: Message text to send
    
    Returns:
        bool: True if message sent successfully, False otherwise
    """
    # Normalize mobile number
    mobile = mobile.strip()
    if not mobile.startswith("+91"):
        if mobile.startswith("91"):
            mobile = "+" + mobile
        elif mobile.startswith("0"):
            mobile = "+91" + mobile[1:]
        else:
            mobile = "+91" + mobile
    
    # Remove any spaces or dashes
    mobile = mobile.replace(" ", "").replace("-", "")
    
    # Get driver
    driver = get_whatsapp_driver(hospital_id)
    if not driver:
        logger.error(f"Cannot send message: No active WhatsApp session for hospital {hospital_id}")
        return False
    
    # Send message (with hospital_id for logging)
    return send_whatsapp_message(driver, mobile, message, hospital_id=hospital_id)


def check_whatsapp_session_health(hospital_id: int) -> bool:
    """
    Check if WhatsApp session is still active and healthy.
    
    Returns:
        bool: True if session is active, False otherwise
    """
    if hospital_id not in _driver_sessions:
        return False
    
    try:
        driver = _driver_sessions[hospital_id]
        driver.current_url
        return True
    except Exception:
        # Session expired
        if hospital_id in _driver_sessions:
            del _driver_sessions[hospital_id]
        return False


def close_whatsapp_session(hospital_id: int):
    """Close WhatsApp session for a hospital."""
    if hospital_id in _driver_sessions:
        try:
            _driver_sessions[hospital_id].quit()
        except Exception:
            pass
        del _driver_sessions[hospital_id]
        logger.info(f"WhatsApp session closed for hospital {hospital_id}")

