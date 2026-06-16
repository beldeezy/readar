"""
Email utility for sending notifications using Resend.

Resend integration for sending weekly pending books reports.
Set RESEND_API_KEY in your .env file to enable email sending.
"""
import logging
import os
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import PendingBook

logger = logging.getLogger(__name__)

# Try to import Resend, but don't fail if it's not installed
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend library not installed. Email sending will be logged only.")

EMAIL_FROM = "Readar <auth@readar.ai>"


def _app_url() -> str:
    """Public app URL for email CTAs (first FRONTEND_ORIGINS entry, or default)."""
    from app.core.config import settings
    raw = getattr(settings, "FRONTEND_ORIGINS", None)
    if raw and raw.strip():
        first = raw.split(",")[0].strip()
        if first:
            return first.rstrip("/")
    return "https://readar.ai"


def _send_email(recipient: str, subject: str, html: str) -> dict:
    """Low-level Resend send with graceful no-op when not configured."""
    from app.core.config import settings
    api_key = settings.RESEND_API_KEY
    if not RESEND_AVAILABLE or not api_key:
        logger.info("[EMAIL] (not sent — Resend unconfigured) to=%s subject=%s", recipient, subject)
        return {"status": "skipped", "message": "Resend not configured", "recipient": recipient}
    try:
        resend.api_key = api_key
        response = resend.Emails.send({
            "from": EMAIL_FROM,
            "to": [recipient],
            "subject": subject,
            "html": html,
        })
        return {"status": "success", "recipient": recipient, "email_id": response.get("id")}
    except Exception as e:
        logger.exception("[EMAIL] Failed to send to %s", recipient)
        return {"status": "error", "recipient": recipient, "message": str(e)}


def build_recommendations_email_html(name: Optional[str], books: list, app_url: Optional[str] = None) -> str:
    """Render the 'your next reads' re-engagement email from RecommendationItem-like objects."""
    app_url = app_url or _app_url()
    greeting = f"Hi {name}," if name else "Hi,"

    def book_block(b) -> str:
        title = getattr(b, "title", None) or (b.get("title") if isinstance(b, dict) else "")
        author = getattr(b, "author_name", None) or (b.get("author_name") if isinstance(b, dict) else "")
        promise = (
            getattr(b, "promise", None) or getattr(b, "best_for", None)
            or (b.get("promise") or b.get("best_for") if isinstance(b, dict) else "")
            or ""
        )
        author_line = f'<div style="color:#667085;font-size:14px;margin:2px 0 6px;">by {author}</div>' if author else ""
        promise_line = f'<div style="color:#475467;font-size:14px;line-height:1.5;">{promise}</div>' if promise else ""
        return (
            f'<tr><td style="padding:14px 0;border-bottom:1px solid #ECECEC;">'
            f'<div style="font-size:16px;font-weight:600;color:#111315;">{title}</div>'
            f'{author_line}{promise_line}</td></tr>'
        )

    rows = "".join(book_block(b) for b in books)
    return f"""\
<html><body style="margin:0;background:#F6F4EF;padding:24px;font-family:Inter,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;margin:0 auto;background:#fff;border-radius:14px;border:1px solid #E5E7EB;">
    <tr><td style="padding:28px 28px 8px;">
      <div style="font-size:20px;font-weight:700;color:#111315;">Your next reads are ready</div>
      <p style="color:#475467;font-size:15px;line-height:1.6;margin:10px 0 0;">{greeting} based on your stage, focus, and reading history, here are a few books worth your time:</p>
    </td></tr>
    <tr><td style="padding:4px 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table></td></tr>
    <tr><td style="padding:20px 28px 28px;">
      <a href="{app_url}/recommendations" style="display:inline-block;background:#111315;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 22px;border-radius:10px;">See your recommendations →</a>
      <p style="color:#98A2B3;font-size:12px;line-height:1.5;margin:22px 0 0;">You're receiving this because email recommendations are on. Manage this in your <a href="{app_url}/profile" style="color:#0E7490;">profile</a>.</p>
    </td></tr>
  </table>
</body></html>"""


def send_recommendations_email(recipient: str, name: Optional[str], books: list) -> dict:
    """Send the 'your next reads' email to one recipient."""
    if not books:
        return {"status": "skipped", "message": "no books", "recipient": recipient}
    html = build_recommendations_email_html(name, books)
    return _send_email(recipient, "Your next reads are ready", html)


def generate_weekly_pending_books_report(db: Session) -> str:
    """
    Generate HTML email report of new books added to pending_books in the past week.

    Args:
        db: Database session

    Returns:
        HTML string for email body
    """
    # Calculate date range (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)

    # Query pending books added in the last week
    new_books = db.query(PendingBook).filter(
        PendingBook.created_at >= week_ago,
        PendingBook.added_to_catalog == False
    ).order_by(PendingBook.created_at.desc()).all()

    if not new_books:
        return """
        <html>
            <body>
                <h2>Readar Weekly Book Report</h2>
                <p>No new books were added to the pending queue this week.</p>
                <p><em>Report generated: {}</em></p>
            </body>
        </html>
        """.format(datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

    # Build HTML report
    book_rows = ""
    for book in new_books:
        book_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{book.title}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{book.author}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{book.isbn or 'N/A'}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{book.isbn13 or 'N/A'}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{book.year_published or 'N/A'}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{book.num_pages or 'N/A'}</td>
            <td style="padding: 8px; border-bottom: 1px solid #ddd;">
                {'<a href="' + book.goodreads_url + '">View</a>' if book.goodreads_url else 'N/A'}
            </td>
        </tr>
        """

    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th {{ background-color: #054745; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 8px; }}
                .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <h2>Readar Weekly Book Report</h2>
            <div class="summary">
                <strong>{len(new_books)} new book(s)</strong> added to the pending queue this week
                (from {week_ago.strftime("%Y-%m-%d")} to {datetime.utcnow().strftime("%Y-%m-%d")})
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>Author</th>
                        <th>ISBN</th>
                        <th>ISBN13</th>
                        <th>Year</th>
                        <th>Pages</th>
                        <th>Goodreads</th>
                    </tr>
                </thead>
                <tbody>
                    {book_rows}
                </tbody>
            </table>

            <p style="margin-top: 30px; color: #666; font-size: 12px;">
                <em>Report generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</em>
            </p>
        </body>
    </html>
    """

    return html


def send_weekly_pending_books_email(db: Session, recipient: str = "michael@readar.ai") -> dict:
    """
    Send weekly report of new pending books using Resend.

    Args:
        db: Database session
        recipient: Email address to send report to

    Returns:
        Dict with status and message
    """
    try:
        # Generate report content
        html_content = generate_weekly_pending_books_report(db)

        # Check if Resend is configured
        from app.core.config import settings
        api_key = settings.RESEND_API_KEY

        if not RESEND_AVAILABLE:
            logger.warning("[WEEKLY EMAIL] Resend library not installed. Install with: pip install resend")
            logger.info(f"[WEEKLY EMAIL REPORT] Would send to: {recipient}")
            logger.info(f"[WEEKLY EMAIL REPORT] Content:\n{html_content}")
            return {
                "status": "logged",
                "message": "Email content logged (Resend not installed)",
                "recipient": recipient,
            }

        if not api_key:
            logger.warning("[WEEKLY EMAIL] RESEND_API_KEY not set in .env file")
            logger.info(f"[WEEKLY EMAIL REPORT] Would send to: {recipient}")
            logger.info(f"[WEEKLY EMAIL REPORT] Content:\n{html_content}")
            return {
                "status": "logged",
                "message": "Email content logged (RESEND_API_KEY not configured)",
                "recipient": recipient,
            }

        # Send email using Resend
        resend.api_key = api_key

        params = {
            "from": "auth@readar.ai",
            "to": [recipient],
            "subject": "Readar Weekly Book Report",
            "html": html_content,
        }

        response = resend.Emails.send(params)
        logger.info(f"[WEEKLY EMAIL] Successfully sent to {recipient}. Response: {response}")

        return {
            "status": "success",
            "message": f"Weekly report sent successfully to {recipient}",
            "recipient": recipient,
            "email_id": response.get("id"),
        }

    except Exception as e:
        logger.exception("Failed to send weekly pending books report")
        return {
            "status": "error",
            "message": str(e),
        }
