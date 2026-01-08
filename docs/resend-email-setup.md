# Resend Email Setup for Readar

## Overview

Readar now uses [Resend](https://resend.com) for sending weekly email reports about new books added to the pending queue. This guide will help you configure Resend for production use.

## Why Resend?

- **Simple API** - Just one API call to send emails
- **Domain Verified** - Send from your own domain (auth@readar.ai)
- **Reliable** - Built on AWS SES with high deliverability
- **Developer Friendly** - Great documentation and Python SDK
- **Affordable** - 3,000 emails/month free, then $20/month for 50,000

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This installs `resend==2.0.0` along with other dependencies.

### 2. Get Your Resend API Key

1. Go to [https://resend.com](https://resend.com) and sign up
2. Verify your account
3. Go to [API Keys](https://resend.com/api-keys)
4. Click "Create API Key"
5. Give it a name like "Readar Production"
6. Copy the API key (starts with `re_`)

### 3. Verify Your Domain

To send from `auth@readar.ai`, you need to verify your domain:

1. Go to [Domains](https://resend.com/domains) in Resend
2. Click "Add Domain"
3. Enter `readar.ai`
4. Add the DNS records shown to your domain registrar
5. Wait for verification (usually 5-10 minutes)

**DNS Records to Add:**

Resend will provide you with TXT and CNAME records. They'll look something like:

```
Type: TXT
Name: @
Value: resend-verify=abc123...

Type: CNAME
Name: resend._domainkey
Value: resend1.resend.com
```

Add these to your DNS provider (GoDaddy, Cloudflare, etc.).

### 4. Configure Backend

Add your Resend API key to `backend/.env`:

```bash
# Email configuration (Resend)
RESEND_API_KEY=re_your_actual_api_key_here
```

**IMPORTANT:**
- Do NOT commit `.env` files to git
- The API key is sensitive - keep it secret
- Use different API keys for dev/staging/production

### 5. Test Email Sending

#### Option A: Manual Test via Endpoint

```bash
# Make sure backend is running
cd backend
uvicorn app.main:app --reload

# In another terminal, trigger the weekly report
curl -X POST http://localhost:8000/api/reading-history/weekly-report \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

#### Option B: Test via Python

```python
from app.database import SessionLocal
from app.utils.email import send_weekly_pending_books_email

db = SessionLocal()
result = send_weekly_pending_books_email(db, recipient="your-email@example.com")
print(result)
db.close()
```

You should receive an email at michael@readar.ai (or your test email) with the weekly report!

### 6. Verify It's Working

Check the backend logs for:

```
[WEEKLY EMAIL] Successfully sent to michael@readar.ai. Response: {'id': 're_...'}
```

If you see this, emails are being sent successfully!

## Current Behavior

### With Resend Configured

- Emails sent to `michael@readar.ai` every Monday at 9:00 AM UTC
- From address: `auth@readar.ai`
- Subject: "Readar Weekly Book Report"
- Contains HTML table with all new books from past 7 days

### Without Resend Configured

- Email content is logged to console
- No actual emails sent
- Logs show: `[WEEKLY EMAIL REPORT] Would send to: michael@readar.ai`

## Troubleshooting

### "Resend library not installed"

```bash
pip install resend==2.0.0
```

### "RESEND_API_KEY not set in .env file"

Make sure you added it to `backend/.env`:

```bash
RESEND_API_KEY=re_your_key_here
```

### "Domain not verified"

Check your domain verification status:
1. Go to [Resend Domains](https://resend.com/domains)
2. Make sure `readar.ai` shows as "Verified"
3. If not, check DNS records are correct

### Emails Not Received

1. Check spam folder
2. Verify domain is verified in Resend
3. Check Resend logs: [https://resend.com/emails](https://resend.com/emails)
4. Make sure `auth@readar.ai` is a valid sender

## Production Deployment

When deploying to production (Render, Heroku, etc.):

1. Add `RESEND_API_KEY` as an environment variable
2. Use the production API key (not dev key)
3. Make sure domain is verified before going live
4. Monitor email sends in Resend dashboard

### Example: Render Deployment

```bash
# In your Render dashboard
# Go to Environment Variables
# Add:
RESEND_API_KEY=re_your_production_key
```

## Monitoring

- **Resend Dashboard**: [https://resend.com/emails](https://resend.com/emails)
- **Backend Logs**: Check for `[WEEKLY EMAIL]` log messages
- **Weekly Reports**: Should arrive every Monday at 9 AM UTC

## Cost Estimate

- **Free Tier**: 3,000 emails/month
- **Weekly Reports**: ~4 emails/month (1 per week)
- **Well within free tier** - No cost for years!

## Next Steps

1. ✅ Install Resend library
2. ✅ Get API key
3. ✅ Verify domain
4. ✅ Add to `.env`
5. ✅ Test sending
6. ✅ Deploy to production

Once configured, weekly reports will automatically be sent every Monday!

## Support

- **Resend Docs**: [https://resend.com/docs](https://resend.com/docs)
- **Resend Support**: support@resend.com
- **Readar Email Code**: `backend/app/utils/email.py`
