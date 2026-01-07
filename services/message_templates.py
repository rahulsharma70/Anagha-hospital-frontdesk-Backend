"""
Message Templates for WhatsApp Notifications
Hospital-specific customizable message templates
"""
from typing import Optional
from datetime import datetime

def format_date(date_obj) -> str:
    """Format date object to readable string."""
    if isinstance(date_obj, str):
        return date_obj
    try:
        return date_obj.strftime("%d %b %Y")
    except:
        return str(date_obj)


def format_time(time_slot: str) -> str:
    """Format time slot to readable format."""
    try:
        # Convert "10:30" to "10:30 AM" or "14:30" to "2:30 PM"
        hour, minute = map(int, time_slot.split(":"))
        if hour < 12:
            period = "AM"
            if hour == 0:
                hour = 12
        else:
            period = "PM"
            if hour > 12:
                hour -= 12
        
        return f"{hour}:{minute:02d} {period}"
    except:
        return time_slot


def get_confirmation_message(
    patient_name: str,
    doctor_name: str,
    date: str,
    time_slot: str,
    hospital_name: str,
    specialty: Optional[str] = None,
    custom_template: Optional[str] = None
) -> str:
    """
    Generate appointment confirmation message.
    
    Args:
        patient_name: Patient's name
        doctor_name: Doctor's name
        date: Appointment date
        time_slot: Time slot
        hospital_name: Hospital name
        specialty: Specialty (optional)
        custom_template: Custom template from hospital settings
    
    Returns:
        str: Formatted message
    """
    if custom_template:
        # Use custom template with placeholders
        message = custom_template
        message = message.replace("{patient_name}", patient_name)
        message = message.replace("{doctor_name}", doctor_name)
        message = message.replace("{date}", format_date(date))
        message = message.replace("{time}", format_time(time_slot))
        message = message.replace("{hospital_name}", hospital_name)
        if specialty:
            message = message.replace("{specialty}", specialty)
        return message
    
    # Default template - Exact format as required
    # Format: "Hello Rahul, Your appointment with Dr Mehta (Ortho) is confirmed. 🗓 Date: 10 Feb ⏰ Time: 10:30 AM – ABC Hospital"
    specialty_text = f" ({specialty})" if specialty else ""
    
    # Format date as "10 Feb" (day and month only)
    try:
        if isinstance(date, str):
            from datetime import datetime
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = date
        formatted_date = date_obj.strftime("%d %b")  # "10 Feb"
    except:
        formatted_date = format_date(date)
    
    return f"Hello {patient_name},\nYour appointment with Dr {doctor_name}{specialty_text} is confirmed.\n🗓 Date: {formatted_date}\n⏰ Time: {format_time(time_slot)}\n– {hospital_name}"


def get_followup_message(
    patient_name: str,
    doctor_name: str,
    followup_date: str,
    hospital_name: str,
    custom_template: Optional[str] = None
) -> str:
    """
    Generate follow-up reminder message.
    
    Args:
        patient_name: Patient's name
        doctor_name: Doctor's name
        followup_date: Follow-up date
        hospital_name: Hospital name
        custom_template: Custom template from hospital settings
    
    Returns:
        str: Formatted message
    """
    if custom_template:
        message = custom_template
        message = message.replace("{patient_name}", patient_name)
        message = message.replace("{doctor_name}", doctor_name)
        message = message.replace("{followup_date}", format_date(followup_date))
        message = message.replace("{hospital_name}", hospital_name)
        return message
    
    # Default template
    return f"""Hello {patient_name},

This is a reminder for your follow-up visit with Dr {doctor_name}.

📅 Date: {format_date(followup_date)}

– {hospital_name}"""


def get_reminder_message(
    patient_name: str,
    doctor_name: str,
    date: str,
    time_slot: str,
    hospital_name: str,
    custom_template: Optional[str] = None
) -> str:
    """
    Generate appointment reminder message (for upcoming appointments).
    
    Args:
        patient_name: Patient's name
        doctor_name: Doctor's name
        date: Appointment date
        time_slot: Time slot
        hospital_name: Hospital name
        custom_template: Custom template from hospital settings
    
    Returns:
        str: Formatted message
    """
    if custom_template:
        message = custom_template
        message = message.replace("{patient_name}", patient_name)
        message = message.replace("{doctor_name}", doctor_name)
        message = message.replace("{date}", format_date(date))
        message = message.replace("{time}", format_time(time_slot))
        message = message.replace("{hospital_name}", hospital_name)
        return message
    
    # Default template
    return f"""Hello {patient_name},

Reminder: Your appointment with Dr {doctor_name} is scheduled for:

🗓 Date: {format_date(date)}
⏰ Time: {format_time(time_slot)}

Please arrive on time.

– {hospital_name}"""

