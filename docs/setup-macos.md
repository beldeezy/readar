# Setting Up Readar Backend on macOS

## Step 1: Check Python Installation

```bash
python3 --version
```

If you don't have Python 3, install it:
```bash
# Using Homebrew (recommended)
brew install python3

# Verify installation
python3 --version
pip3 --version
```

## Step 2: Create Virtual Environment

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# You should see (venv) in your terminal prompt now
```

## Step 3: Install Dependencies

```bash
# With virtual environment activated
pip install -r requirements.txt
```

## Step 4: Set Up Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your actual values
# At minimum, set DATABASE_URL
nano .env
```

Example `.env`:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/readar
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_JWT_SECRET=your_jwt_secret
```

## Step 5: Run Database Migration

```bash
# Make sure virtual environment is activated
alembic upgrade head
```

## Step 6: Start Backend Server

```bash
# Start the backend
uvicorn app.main:app --reload

# You should see:
# [SCHEDULER] Background scheduler started successfully
```

## Step 7: Test Chat Onboarding

In another terminal:
```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173 and test the onboarding flow.

## Deactivating Virtual Environment

When you're done:
```bash
deactivate
```

## Quick Commands (After Initial Setup)

```bash
# Start backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Start frontend (in another terminal)
cd frontend
npm run dev
```
