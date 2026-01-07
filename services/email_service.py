"""
Email Service with per-hospital SMTP configuration
Supports both hospital-specific and global SMTP settings
"""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict
from database import get_supabase
import config
import logging

logger = logging.getLogger(__name__)


def get_hospital_smtp_config(hospital_id: Optional[int] = None) -> Dict:
    """
    Get SMTP configuration for a hospital.
    Falls back to global config if hospital doesn't have custom settings.
    
    Returns:
        Dict with SMTP configuration keys: host, port, username, password, from_email, use_ssl, enabled
    """
    supabase = get_supabase()
    
    if hospital_id and supabase:
        try:
            result = supabase.table("hospitals").select(
                "smtp_host, smtp_port, smtp_username, smtp_password, "
                "smtp_from_email, smtp_enabled, smtp_use_ssl"
            ).eq("id", hospital_id).execute()
            
            if result.data and result.data[0].get("smtp_enabled"):
                hospital_config = result.data[0]
                # Only return config if all required fields are present
                if hospital_config.get("smtp_host") and hospital_config.get("smtp_username"):
                    return {
                        "host": hospital_config.get("smtp_host"),
                        "port": hospital_config.get("smtp_port") or 587,
                        "username": hospital_config.get("smtp_username"),
                        "password": hospital_config.get("smtp_password"),
                        "from_email": hospital_config.get("smtp_from_email") or hospital_config.get("smtp_username"),
                        "use_ssl": hospital_config.get("smtp_use_ssl", False),
                        "enabled": True
                    }
        except Exception as e:
            logger.error(f"Error fetching hospital SMTP config for hospital {hospital_id}: {e}")
    
    # Fallback to global config
    return {
        "host": config.SMTP_HOST,
        "port": config.SMTP_PORT,
        "username": config.SMTP_USERNAME,
        "password": config.SMTP_PASSWORD,
        "from_email": config.SMTP_FROM_EMAIL or config.SMTP_USERNAME,
        "use_ssl": False,
        "enabled": bool(config.SMTP_HOST and config.SMTP_USERNAME)
    }


async def send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    hospital_id: Optional[int] = None
) -> bool:
    """
    Send email using hospital-specific or global SMTP settings
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body_text: Plain text email body
        body_html: HTML email body (optional)
        hospital_id: Hospital ID to use hospital-specific SMTP (optional)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    smtp_config = get_hospital_smtp_config(hospital_id)
    
    if not smtp_config.get("enabled"):
        logger.warning(f"SMTP not enabled (hospital_id={hospital_id}), skipping email to {to_email}")
        return False
    
    if not smtp_config.get("host") or not smtp_config.get("username") or not smtp_config.get("password"):
        logger.error(f"SMTP configuration incomplete for hospital {hospital_id}")
        return False
    
    try:
        # Create message
        message = MIMEMultipart("alternative")
        message["From"] = smtp_config["from_email"]
        message["To"] = to_email
        message["Subject"] = subject
        
        # Add plain text part
        text_part = MIMEText(body_text, "plain")
        message.attach(text_part)
        
        # Add HTML part if provided
        if body_html:
            html_part = MIMEText(body_html, "html")
            message.attach(html_part)
        
        # Send email
        if smtp_config["use_ssl"]:
            # SSL connection (port 465)
            await aiosmtplib.send(
                message,
                hostname=smtp_config["host"],
                port=smtp_config["port"],
                username=smtp_config["username"],
                password=smtp_config["password"],
                use_tls=False,
                start_tls=False
            )
        else:
            # TLS connection (port 587)
            await aiosmtplib.send(
                message,
                hostname=smtp_config["host"],
                port=smtp_config["port"],
                username=smtp_config["username"],
                password=smtp_config["password"],
                use_tls=True,
                start_tls=True
            )
        
        logger.info(f"✅ Email sent to {to_email} using {'hospital' if hospital_id else 'global'} SMTP (hospital_id={hospital_id})")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error sending email to {to_email} (hospital_id={hospital_id}): {e}")
        return False


async def send_hospital_registration_email(hospital_data: dict, hospital_id: Optional[int] = None) -> bool:
    """
    Send hospital registration email to admin using hospital's SMTP or global SMTP
    
    Args:
        hospital_data: Dictionary containing hospital registration data
        hospital_id: Hospital ID to use hospital-specific SMTP
    
    Returns:
        True if email sent successfully, False otherwise
    """
    admin_email = config.ADMIN_EMAIL
    
    subject = f"New Hospital Registration Request: {hospital_data.get('name', 'Unknown')}"
    
    body_text = f"""
New Hospital Registration Request

Hospital Details:
-----------------
Name: {hospital_data.get('name', 'N/A')}
Email: {hospital_data.get('email', 'N/A')}
Mobile: {hospital_data.get('mobile', 'N/A')}
Address Line 1: {hospital_data.get('address_line1', 'N/A')}
Address Line 2: {hospital_data.get('address_line2', 'N/A')}
Address Line 3: {hospital_data.get('address_line3', 'N/A')}
City: {hospital_data.get('city', 'N/A')}
State: {hospital_data.get('state', 'N/A')}
Pincode: {hospital_data.get('pincode', 'N/A')}

Payment UPI IDs:
----------------
Default UPI ID: {hospital_data.get('upi_id', 'N/A')}
Google Pay: {hospital_data.get('gpay_upi_id', 'N/A')}
PhonePe: {hospital_data.get('phonepay_upi_id', 'N/A')}
Paytm: {hospital_data.get('paytm_upi_id', 'N/A')}
BHIM UPI: {hospital_data.get('bhim_upi_id', 'N/A')}

Registration Date: {hospital_data.get('registration_date', 'N/A')}
Hospital ID: {hospital_data.get('id', 'N/A')}

Please review and approve/reject this registration.
"""
    
    body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .section {{ margin: 20px 0; padding: 15px; background-color: #f9f9f9; border-left: 4px solid #4CAF50; }}
        .label {{ font-weight: bold; color: #555; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>New Hospital Registration Request</h2>
    </div>
    <div class="content">
        <div class="section">
            <h3>Hospital Details</h3>
            <p><span class="label">Name:</span> {hospital_data.get('name', 'N/A')}</p>
            <p><span class="label">Email:</span> {hospital_data.get('email', 'N/A')}</p>
            <p><span class="label">Mobile:</span> {hospital_data.get('mobile', 'N/A')}</p>
            <p><span class="label">Address:</span> {hospital_data.get('address_line1', 'N/A')}</p>
            <p><span class="label">City:</span> {hospital_data.get('city', 'N/A')}</p>
            <p><span class="label">State:</span> {hospital_data.get('state', 'N/A')}</p>
            <p><span class="label">Pincode:</span> {hospital_data.get('pincode', 'N/A')}</p>
            <p><span class="label">Hospital ID:</span> {hospital_data.get('id', 'N/A')}</p>
        </div>
    </div>
</body>
</html>
"""
    
    return await send_email(
        to_email=admin_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        hospital_id=hospital_id
    )

