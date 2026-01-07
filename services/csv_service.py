"""
CSV Export Service for Appointments
Exports appointment data to CSV files with +91 mobile prefix
"""
import csv
import os
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Directory for CSV files
# CSV export directory - relative to backend directory
import os
from pathlib import Path
BACKEND_DIR = Path(__file__).parent.parent
CSV_DIR = str(BACKEND_DIR / "appointment_exports")

def ensure_csv_directory():
    """Ensure CSV directory exists."""
    os.makedirs(CSV_DIR, exist_ok=True)


def normalize_mobile(mobile: str) -> str:
    """
    Normalize mobile number to include +91 prefix.
    
    Args:
        mobile: Mobile number in any format
    
    Returns:
        str: Mobile number with +91 prefix
    """
    mobile = mobile.strip().replace(" ", "").replace("-", "")
    
    if mobile.startswith("+91"):
        return mobile
    elif mobile.startswith("91") and len(mobile) == 12:
        return "+" + mobile
    elif mobile.startswith("0"):
        return "+91" + mobile[1:]
    else:
        return "+91" + mobile


def save_appointment_csv(hospital_id: int, appointment_data: Dict) -> bool:
    """
    Save appointment data to CSV file.
    Appends to existing file (never overwrites).
    
    Format: name,mobile,date,time_slot,doctor,specialty,followup_date
    
    Logic Rules:
    - Always prefix mobile with +91
    - Append data (never overwrite)
    
    Args:
        hospital_id: Hospital ID
        appointment_data: Dictionary with appointment fields:
            - name: Patient name
            - mobile: Mobile number
            - date: Appointment date
            - time_slot: Time slot
            - doctor: Doctor name
            - specialty: Specialty (optional)
            - followup_date: Follow-up date (optional)
    
    Returns:
        bool: True if saved successfully
    """
    try:
        ensure_csv_directory()
        
        # Filename format: hospital_{hospital_id}_appointments.csv
        filename = f"{CSV_DIR}/hospital_{hospital_id}_appointments.csv"
        file_exists = os.path.exists(filename)
        
        # Normalize mobile number - Always prefix with +91
        mobile = appointment_data.get("mobile", "")
        if not mobile.startswith("+91"):
            mobile = "+91" + mobile
        
        # Prepare row data in exact format: name,mobile,date,time_slot,doctor,specialty,followup_date
        row = [
            appointment_data.get("name", ""),
            mobile,
            appointment_data.get("date", ""),
            appointment_data.get("time_slot", ""),
            appointment_data.get("doctor", ""),
            appointment_data.get("specialty", ""),
            appointment_data.get("followup_date", "")
        ]
        
        # Write to CSV - Append mode (never overwrite)
        with open(filename, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            
            # Write header if file is new
            if not file_exists:
                header = ["name", "mobile", "date", "time_slot", "doctor", "specialty", "followup_date"]
                writer.writerow(header)
            
            # Append row (never overwrite)
            writer.writerow(row)
        
        logger.info(f"Appointment saved to CSV: {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving appointment to CSV: {str(e)}")
        return False


def get_appointments_csv(hospital_id: int) -> Optional[str]:
    """
    Get path to hospital's CSV file.
    
    Returns:
        str: Path to CSV file, or None if doesn't exist
    """
    filename = f"{CSV_DIR}/hospital_{hospital_id}_appointments.csv"
    if os.path.exists(filename):
        return filename
    return None

