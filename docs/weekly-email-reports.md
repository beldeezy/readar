# Weekly Email Reports for Pending Books

## Overview

The system now includes automatic weekly email reports that notify `michael@readar.ai` about new books added to the pending queue from Goodreads CSV uploads.

## How It Works

### Automatic Scheduling

- **Schedule**: Every Monday at 9:00 AM UTC
- **Recipient**: michael@readar.ai
- **Content**: HTML email with all new books added to `pending_books` table in the past 7 days
- **Trigger**: Runs automatically via background scheduler (APScheduler)

### Email Content

The email includes:
- Summary count of new books
- Date range (past 7 days)
- Table with book details:
  - Title
  - Author
  - ISBN / ISBN13
  - Year published
  - Number of pages
  - Link to Goodreads page (if available)

### Implementation

1. **Scheduler** (`backend/app/scheduler.py`)
   - Background job that runs on a cron schedule
   - Started on FastAPI startup, stopped on shutdown
   - Uses APScheduler's `BackgroundScheduler`

2. **Email Utility** (`backend/app/utils/email.py`)
   - `generate_weekly_pending_books_report()` - Creates HTML email
   - `send_weekly_pending_books_email()` - Sends (or logs) the email

3. **Manual Trigger** (`POST /api/reading-history/weekly-report`)
   - Endpoint to manually trigger the weekly report
   - Useful for testing or ad-hoc reports

## Current Status

✅ **Implemented:**
- Background scheduler with weekly cron job
- HTML email report generation
- Database query for new books from past 7 days
- Automatic deduplication of books
- Manual trigger endpoint

⚠️ **Not Yet Configured:**
- **SMTP Email Sending**: Currently logs email content instead of sending

## Configuring SMTP (Production)

To enable actual email sending, update `backend/app/utils/email.py` with one of these options:

### Option 1: Gmail SMTP

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

msg = MIMEMultipart('alternative')
msg['Subject'] = 'Readar Weekly Book Report'
msg['From'] = 'noreply@readar.ai'
msg['To'] = recipient

html_part = MIMEText(html_content, 'html')
msg.attach(html_part)

with smtplib.SMTP('smtp.gmail.com', 587) as server:
    server.starttls()
    server.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
    server.send_message(msg)
```

Add to `.env`:
```
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
```

### Option 2: SendGrid API

```bash
pip install sendgrid
```

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

message = Mail(
    from_email='noreply@readar.ai',
    to_emails=recipient,
    subject='Readar Weekly Book Report',
    html_content=html_content
)

sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
response = sg.send(message)
```

Add to `.env`:
```
SENDGRID_API_KEY=your-api-key
```

### Option 3: AWS SES

```bash
pip install boto3
```

```python
import boto3

client = boto3.client('ses', region_name='us-east-1')

response = client.send_email(
    Source='noreply@readar.ai',
    Destination={'ToAddresses': [recipient]},
    Message={
        'Subject': {'Data': 'Readar Weekly Book Report'},
        'Body': {'Html': {'Data': html_content}}
    }
)
```

## Testing

### Test the Email Generation

```bash
# Start the backend
cd backend
python -m uvicorn app.main:app --reload

# In another terminal, trigger the manual endpoint
curl -X POST http://localhost:8000/api/reading-history/weekly-report \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check the logs for the generated email content
```

### Test the Scheduler

When the backend starts, you should see:
```
[SCHEDULER] Background scheduler started successfully
```

The scheduler will run automatically every Monday at 9:00 AM UTC. For immediate testing, you can:

1. Modify `app/scheduler.py` to run more frequently (e.g., every minute for testing):
   ```python
   scheduler.add_job(
       send_weekly_report_job,
       trigger=CronTrigger(minute='*'),  # Every minute
       ...
   )
   ```

2. Or call the manual endpoint to test immediately

## Database Migration

Before the system can store pending books, run the migration:

```bash
cd backend
alembic upgrade head
```

This creates the `pending_books` table with columns for:
- Book metadata (title, author, ISBNs, Goodreads data)
- Catalog status tracking
- Timestamps for reporting

## Book Deduplication

The CSV upload automatically deduplicates books by checking:
1. **ISBN-10** match with `books.isbn_10`
2. **ISBN-13** match with `books.isbn_13`
3. **Title + Author** (case-insensitive) match

Books already in the main catalog are counted as "imported" but not added to the pending queue.

## Future Enhancements

- [ ] Configure SMTP for production email sending
- [ ] Add email template customization
- [ ] Include statistics (total pending books, catalog growth)
- [ ] Add email preferences for recipients
- [ ] Create admin dashboard to view pending books
- [ ] Implement automatic catalog addition workflow
