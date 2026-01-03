"""
Email utility for sending notifications.

TODO: Configure SMTP settings in .env or integrate with an email service like SendGrid/Mailgun.
For now, this logs email content and provides a foundation for integration.
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import PendingBook

logger = logging.getLogger(__name__)


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
    Send weekly report of new pending books.

    Args:
        db: Database session
        recipient: Email address to send report to

    Returns:
        Dict with status and message
    """
    try:
        # Generate report content
        html_content = generate_weekly_pending_books_report(db)

        # TODO: Implement actual email sending via SMTP or email service
        # For now, we'll log the email content and mark as sent

        logger.info(f"[WEEKLY EMAIL REPORT] Would send to: {recipient}")
        logger.info(f"[WEEKLY EMAIL REPORT] Content:\n{html_content}")

        # In production, this would use SMTP or an email service like:
        # - SendGrid API
        # - Mailgun API
        # - AWS SES
        # - Standard SMTP (Gmail, etc.)

        # Example placeholder for future implementation:
        # import smtplib
        # from email.mime.text import MIMEText
        # from email.mime.multipart import MIMEMultipart
        #
        # msg = MIMEMultipart('alternative')
        # msg['Subject'] = 'Readar Weekly Book Report'
        # msg['From'] = 'noreply@readar.ai'
        # msg['To'] = recipient
        #
        # html_part = MIMEText(html_content, 'html')
        # msg.attach(html_part)
        #
        # with smtplib.SMTP(smtp_host, smtp_port) as server:
        #     server.starttls()
        #     server.login(smtp_user, smtp_password)
        #     server.send_message(msg)

        return {
            "status": "success",
            "message": f"Weekly report generated and logged (email sending not yet configured). Check logs for content.",
            "recipient": recipient,
        }

    except Exception as e:
        logger.exception("Failed to generate/send weekly pending books report")
        return {
            "status": "error",
            "message": str(e),
        }
