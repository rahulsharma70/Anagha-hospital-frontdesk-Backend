"""
Background scheduler for sending WhatsApp reminders and follow-ups
Uses APScheduler for reliable background job execution
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from database import get_supabase
from services.audit_logger import log_message_send
from services.error_monitoring import capture_exception
import logging

logger = logging.getLogger(__name__)

# Configure scheduler
jobstores = {
    'default': MemoryJobStore()
}
executors = {
    'default': ThreadPoolExecutor(20)
}
job_defaults = {
    'coalesce': False,
    'max_instances': 3,
    'misfire_grace_time': 300  # 5 minutes
}

scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    executors=executors,
    job_defaults=job_defaults,
    timezone='Asia/Kolkata'
)


def start_scheduler():
    """Start the scheduler"""
    try:
        if not scheduler.running:
            scheduler.start()
            logger.info("✅ Background scheduler started")
            
            # Add scheduled jobs
            add_scheduled_jobs()
        else:
            logger.info("ℹ️ Scheduler already running")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
        capture_exception(e)


def shutdown_scheduler():
    """Shutdown the scheduler gracefully"""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logger.info("✅ Background scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error shutting down scheduler: {e}")
        capture_exception(e)


def add_scheduled_jobs():
    """Add all scheduled background jobs"""
    try:
        # Daily reminder job - runs every day at 9:00 AM
        scheduler.add_job(
            send_daily_reminders,
            trigger=CronTrigger(hour=9, minute=0),
            id='daily_reminders',
            name='Send daily appointment reminders',
            replace_existing=True
        )
        
        # Follow-up job - runs every day at 6:00 PM
        scheduler.add_job(
            send_follow_up_messages,
            trigger=CronTrigger(hour=18, minute=0),
            id='follow_up_messages',
            name='Send follow-up messages',
            replace_existing=True
        )
        
        # Check pending messages - runs every hour
        scheduler.add_job(
            process_pending_messages,
            trigger=IntervalTrigger(hours=1),
            id='process_pending_messages',
            name='Process pending WhatsApp messages',
            replace_existing=True
        )
        
        logger.info("✅ Scheduled jobs added to scheduler")
    except Exception as e:
        logger.error(f"❌ Failed to add scheduled jobs: {e}")
        capture_exception(e)


def send_daily_reminders():
    """Send reminders for appointments/operations scheduled for today"""
    try:
        supabase = get_supabase()
        if not supabase:
            logger.warning("⚠️ Supabase not available, skipping reminders")
            return
        
        today = datetime.now().date().isoformat()
        
        # Get appointments scheduled for today
        appointments = supabase.table("appointments").select("*").eq("date", today).eq("status", "confirmed").execute()
        
        if appointments.data:
            from services.whatsapp_service import send_appointment_reminder
            for apt in appointments.data:
                try:
                    send_appointment_reminder(apt)
                    log_message_send(
                        user_id=apt.get("patient_id"),
                        message_type="whatsapp",
                        recipient=apt.get("patient_mobile", ""),
                        subject_or_purpose="Appointment reminder",
                        success=True
                    )
                except Exception as e:
                    logger.error(f"Error sending reminder for appointment {apt.get('id')}: {e}")
                    log_message_send(
                        user_id=apt.get("patient_id"),
                        message_type="whatsapp",
                        recipient=apt.get("patient_mobile", ""),
                        subject_or_purpose="Appointment reminder",
                        success=False,
                        error_message=str(e)
                    )
        
        # Get operations scheduled for today
        operations = supabase.table("operations").select("*").eq("operation_date", today).eq("status", "confirmed").execute()
        
        if operations.data:
            from services.whatsapp_service import send_operation_reminder
            for op in operations.data:
                try:
                    send_operation_reminder(op)
                    log_message_send(
                        user_id=op.get("patient_id"),
                        message_type="whatsapp",
                        recipient=op.get("patient_mobile", ""),
                        subject_or_purpose="Operation reminder",
                        success=True
                    )
                except Exception as e:
                    logger.error(f"Error sending reminder for operation {op.get('id')}: {e}")
                    log_message_send(
                        user_id=op.get("patient_id"),
                        message_type="whatsapp",
                        recipient=op.get("patient_mobile", ""),
                        subject_or_purpose="Operation reminder",
                        success=False,
                        error_message=str(e)
                    )
        
        logger.info(f"✅ Daily reminders processed: {len(appointments.data or [])} appointments, {len(operations.data or [])} operations")
    except Exception as e:
        logger.error(f"❌ Error in send_daily_reminders: {e}")
        capture_exception(e)


def send_follow_up_messages():
    """Send follow-up messages for completed appointments/operations"""
    try:
        supabase = get_supabase()
        if not supabase:
            logger.warning("⚠️ Supabase not available, skipping follow-ups")
            return
        
        yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
        
        # Get completed appointments from yesterday
        appointments = supabase.table("appointments").select("*").eq("date", yesterday).eq("status", "confirmed").execute()
        
        if appointments.data:
            from services.whatsapp_service import send_follow_up
            for apt in appointments.data:
                try:
                    send_follow_up(apt, "appointment")
                    log_message_send(
                        user_id=apt.get("patient_id"),
                        message_type="whatsapp",
                        recipient=apt.get("patient_mobile", ""),
                        subject_or_purpose="Appointment follow-up",
                        success=True
                    )
                except Exception as e:
                    logger.error(f"Error sending follow-up for appointment {apt.get('id')}: {e}")
        
        logger.info(f"✅ Follow-up messages processed: {len(appointments.data or [])} appointments")
    except Exception as e:
        logger.error(f"❌ Error in send_follow_up_messages: {e}")
        capture_exception(e)


def process_pending_messages():
    """Process pending WhatsApp messages"""
    try:
        supabase = get_supabase()
        if not supabase:
            return
        
        # Get pending messages from whatsapp_logs
        pending = supabase.table("whatsapp_logs").select("*").eq("status", "pending").limit(50).execute()
        
        if pending.data:
            from services.whatsapp_service import send_message
            for msg in pending.data:
                try:
                    send_message(msg["recipient"], msg["message"])
                    # Update status
                    supabase.table("whatsapp_logs").update({"status": "sent"}).eq("id", msg["id"]).execute()
                except Exception as e:
                    logger.error(f"Error processing pending message {msg.get('id')}: {e}")
                    # Update status to failed
                    supabase.table("whatsapp_logs").update({"status": "failed", "error_message": str(e)}).eq("id", msg["id"]).execute()
    except Exception as e:
        logger.error(f"❌ Error in process_pending_messages: {e}")
        capture_exception(e)


def schedule_one_time_reminder(appointment_id: int, reminder_time: datetime):
    """Schedule a one-time reminder for a specific appointment"""
    try:
        scheduler.add_job(
            send_single_reminder,
            trigger='date',
            run_date=reminder_time,
            args=[appointment_id],
            id=f'reminder_{appointment_id}',
            replace_existing=True
        )
        logger.info(f"✅ One-time reminder scheduled for appointment {appointment_id} at {reminder_time}")
    except Exception as e:
        logger.error(f"❌ Failed to schedule reminder: {e}")
        capture_exception(e)


def send_single_reminder(appointment_id: int):
    """Send reminder for a specific appointment"""
    try:
        supabase = get_supabase()
        if not supabase:
            return
        
        appointment = supabase.table("appointments").select("*").eq("id", appointment_id).execute()
        if appointment.data:
            apt = appointment.data[0]
            from services.whatsapp_service import send_appointment_reminder
            send_appointment_reminder(apt)
            log_message_send(
                user_id=apt.get("patient_id"),
                message_type="whatsapp",
                recipient=apt.get("patient_mobile", ""),
                subject_or_purpose="Appointment reminder",
                success=True
            )
    except Exception as e:
        logger.error(f"❌ Error sending single reminder: {e}")
        capture_exception(e)
