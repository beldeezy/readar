# Marketing-Attribution Dashboard

## Purpose
Pulls daily Twitter, GA4, and (future) Loops data into Google Sheets for 
quick marketing insights.

## Quick start
```bash
git clone …
cd marketing-dashboard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

ENV variables
Key	Example	Purpose
GOOGLE_SA_JSON	gservice_account.json	Service-account key
GSHEET_ID	1abc…	Target Sheet
TW_BEARER_TOKEN	AAA…	Twitter API
TW_USER_ID	12345	Twitter numeric ID
GA_BELDEEZY_ID	379561234	GA property
GA_READAR_ID	420987654	GA property

One-time setup
Create Google Sheet, share with service account.

Grant service account Viewer on GA4 properties.

Fill .env.

Test: python src/main.py.

Scheduled jobs
Job	Schedule	File
com.readar.marketingdashboard	daily 23:55 ET	runs pipeline
com.readar.logrotate	Weekly Sun 23:59	rotates logs

Logs
logs/daily.log rotated weekly to daily_YYYYMMDD.log.
