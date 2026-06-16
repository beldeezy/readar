"""
Background scheduler for periodic tasks like weekly email reports.

Uses APScheduler to run tasks in the background.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.utils.email import send_weekly_pending_books_email
from app.services.reengagement import send_recommendation_emails

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def send_weekly_report_job():
    """
    Scheduled job to send weekly pending books report.
    Runs every Monday at 9:00 AM UTC.
    """
    logger.info("Running weekly pending books report job")

    db: Session = SessionLocal()
    try:
        result = send_weekly_pending_books_email(db, recipient="michael@readar.ai")
        logger.info(f"Weekly report job completed: {result}")
    except Exception as e:
        logger.exception(f"Weekly report job failed: {e}")
    finally:
        db.close()


def send_recommendation_emails_job():
    """
    Scheduled job: send the recommendations re-engagement email to eligible,
    opted-in users (frequency-capped). Runs weekly.
    """
    logger.info("Running recommendations re-engagement email job")
    db: Session = SessionLocal()
    try:
        result = send_recommendation_emails(db)
        logger.info(f"Re-engagement email job completed: {result}")
    except Exception as e:
        logger.exception(f"Re-engagement email job failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """
    Start the background scheduler with all configured jobs.
    Call this from the FastAPI startup event.
    """
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already running")
        return

    logger.info("Starting background scheduler")
    scheduler = BackgroundScheduler()

    # Schedule weekly report: Every Monday at 9:00 AM UTC
    scheduler.add_job(
        send_weekly_report_job,
        trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
        id='weekly_pending_books_report',
        name='Send weekly pending books report',
        replace_existing=True
    )

    # Recommendations re-engagement: every Tuesday at 15:00 UTC (~mid-morning US)
    scheduler.add_job(
        send_recommendation_emails_job,
        trigger=CronTrigger(day_of_week='tue', hour=15, minute=0),
        id='recommendation_reengagement_email',
        name='Send recommendations re-engagement email',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Background scheduler started with weekly report + re-engagement jobs")


def stop_scheduler():
    """
    Stop the background scheduler.
    Call this from the FastAPI shutdown event.
    """
    global scheduler

    if scheduler is not None:
        logger.info("Stopping background scheduler")
        scheduler.shutdown()
        scheduler = None
