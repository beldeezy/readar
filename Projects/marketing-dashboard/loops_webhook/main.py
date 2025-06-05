from flask import Flask, request, abort
import os, json, datetime, gspread
from google.oauth2.service_account import Credentials

# ── ENV vars expected in Render dashboard ──────────────────────────
SHEET_ID      = os.getenv("GSHEET_ID")
SA_JSON_B64   = os.getenv("GOOGLE_SA_JSON_B64")       # service-account key, base64
LOOPS_SECRET  = os.getenv("LOOPS_WEBHOOK_SECRET", "") # blank means: no signature check
# ────────────────────────────────────────────────────────────────────

app = Flask(__name__)

# ---- Google Sheets auth ----
import base64, tempfile, pathlib
tmp_key = pathlib.Path(tempfile.gettempdir()) / "sa.json"
tmp_key.write_bytes(base64.b64decode(SA_JSON_B64))

creds = Credentials.from_service_account_file(
    str(tmp_key), scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
gc = gspread.authorize(creds)
ws = gc.open_by_key(SHEET_ID).worksheet("loops_raw")  # create tab manually

# ---- helpers ----
def verify_sig(raw: bytes, sig: str) -> bool:
    if not LOOPS_SECRET:   # founder didn’t give one yet
        return True
    import hmac, hashlib
    mac = hmac.new(LOOPS_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig)

@app.post("/loops")
def loops():
    raw = request.get_data()
    if not verify_sig(raw, request.headers.get("X-Loops-Signature", "")):
        abort(401)

    payload = request.json
    evt     = payload.get("event", "unknown")
    data    = payload.get("data", {})

    row = [
        datetime.datetime.utcnow().isoformat(),
        evt,
        data.get("campaign_name"),
        data.get("emails_sent", 0),
        data.get("emails_opened", 0),
        data.get("emails_clicked", 0),
        data.get("emails_unsubscribed", 0),
        data.get("new_signups", 0),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return "", 204

if __name__ == "__main__":
    app.run(port=8000)
