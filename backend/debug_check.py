#!/usr/bin/env python3
"""
Debug script to check Readar backend configuration
Run this to diagnose issues with scheduler and email setup
"""
import sys
import os

print("=== Readar Backend Debug ===\n")

# Check Python version
print(f"Python version: {sys.version}")
print()

# Check if we're in the right directory
print(f"Current directory: {os.getcwd()}")
print()

# Check for .env file
env_path = "/home/user/readar/backend/.env"
if os.path.exists(env_path):
    print("✓ .env file exists")
    # Try to load it
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print("✓ .env file loaded")
    except Exception as e:
        print(f"✗ Error loading .env: {e}")
else:
    print("✗ .env file NOT found")
print()

# Check environment variables
print("Environment variables:")
resend_key = os.getenv("RESEND_API_KEY")
if resend_key:
    print(f"✓ RESEND_API_KEY is set (starts with: {resend_key[:10]}...)")
else:
    print("✗ RESEND_API_KEY is NOT set")

db_url = os.getenv("DATABASE_URL")
if db_url:
    print(f"✓ DATABASE_URL is set")
else:
    print("✗ DATABASE_URL is NOT set")
print()

# Check required packages
print("Checking required packages:")
packages = [
    ("resend", "Resend email library"),
    ("apscheduler", "Background scheduler"),
    ("fastapi", "FastAPI framework"),
    ("sqlalchemy", "Database ORM"),
]

for package, description in packages:
    try:
        __import__(package)
        print(f"✓ {package} - {description}")
    except ImportError:
        print(f"✗ {package} - {description} (NOT INSTALLED)")
print()

# Try to import app modules
print("Checking app modules:")
try:
    sys.path.insert(0, "/home/user/readar/backend")
    from app.scheduler import start_scheduler
    print("✓ app.scheduler module can be imported")
except Exception as e:
    print(f"✗ app.scheduler import failed: {e}")

try:
    from app.utils.email import send_weekly_pending_books_email
    print("✓ app.utils.email module can be imported")
except Exception as e:
    print(f"✗ app.utils.email import failed: {e}")

try:
    from app.core.config import settings
    print("✓ app.core.config module can be imported")
    print(f"  - RESEND_API_KEY configured: {'Yes' if settings.RESEND_API_KEY else 'No'}")
except Exception as e:
    print(f"✗ app.core.config import failed: {e}")

print()
print("=== Debug Complete ===")
