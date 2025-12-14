# Testing Guide for Readar

This guide will help you test the Readar application end-to-end.

## Prerequisites

1. **PostgreSQL** must be installed and running
2. **Python 3.11+** installed
3. **Node.js 18+** installed

## Step 1: Set Up Backend

### 1.1 Install Backend Dependencies

```bash
cd ~/readar-v1/backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 1.2 Create Database

```bash
# Create PostgreSQL database
createdb readar

# Or using psql:
psql -U postgres
CREATE DATABASE readar;
\q
```

### 1.3 Configure Environment

Create `readar-v1/backend/.env`:

```env
DATABASE_URL=postgresql://postgres:password@localhost/readar
JWT_SECRET_KEY=test-secret-key-for-development-only
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
ENVIRONMENT=development
DEBUG=true
```

**Note:** Replace `postgres:password` with your PostgreSQL credentials.

### 1.4 Run Database Migrations

```bash
cd ~/readar-v1/backend
source venv/bin/activate
alembic upgrade head
```

If this is the first time, you may need to create the initial migration:

```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### 1.5 Seed Books

```bash
cd ~/readar-v1/backend
source venv/bin/activate
python -m app.scripts.seed_books
```

You should see: `✓ Seeded X new books`

### 1.6 Start Backend Server

```bash
cd ~/readar-v1/backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Backend should be running at: `http://localhost:8000`

**Verify:** Open `http://localhost:8000/docs` - you should see the FastAPI documentation.

## Step 2: Set Up Frontend

### 2.1 Install Frontend Dependencies

```bash
cd ~/readar-v1/frontend
npm install
```

### 2.2 Configure Environment

Create `readar-v1/frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 2.3 Start Frontend Server

```bash
cd ~/readar-v1/frontend
npm run dev
```

Frontend should be running at: `http://localhost:5173`

## Step 3: Test the Application

### Test 1: API Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"ok"}
```

### Test 2: Sign Up (API)

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123456"}'
```

Expected response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Save the `access_token` for next steps!**

### Test 3: Login (API)

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123456"}'
```

### Test 4: Get Current User (API)

Replace `YOUR_TOKEN` with the access_token from signup:

```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test 5: Get Books (API)

```bash
curl http://localhost:8000/books?limit=5
```

Should return a list of books.

### Test 6: Complete Onboarding (API)

```bash
curl -X POST http://localhost:8000/onboarding \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Doe",
    "business_model": "SaaS",
    "business_stage": "pre-revenue",
    "biggest_challenge": "Getting my first customers"
  }'
```

### Test 7: Get Recommendations (API)

```bash
curl -X POST http://localhost:8000/recommendations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_results": 5}'
```

Should return a list of recommended books with scores.

### Test 8: Mark Book as Interested (API)

First, get a book ID from the recommendations response, then:

```bash
curl -X POST http://localhost:8000/user-books \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "BOOK_ID_HERE",
    "status": "interesting"
  }'
```

## Step 4: Test Full User Flow (Frontend)

### 4.1 Landing Page
1. Open `http://localhost:5173`
2. Should see landing page with "Get Started" button
3. Click "Get Started"

### 4.2 Sign Up
1. Should see auth page with Sign Up/Log In tabs
2. Enter email and password (min 6 characters)
3. Click "Sign Up"
4. Should redirect to onboarding

### 4.3 Onboarding
1. **Step 1:** Enter name, occupation, location, industry
2. Click "Next"
3. **Step 2:** Enter business model, select business stage, org size
4. Click "Next"
5. **Step 3:** Select areas of business focus, enter biggest challenge
6. Click "Next"
7. **Step 4:** Answer reading history question
8. Click "Get Recommendations"

### 4.4 Recommendations
1. Should see list of recommended books
2. Each book should show:
   - Title, author, categories
   - Score badge (Top Match / Strong Match / Good Match)
   - Action buttons
3. Click "Save as Interested" on a book
4. Click "Not for me" on another book
5. Click on a book title to see details

### 4.5 Book Detail
1. Should see full book information
2. Can mark as read/interested/not interested
3. Click "Back" to return

### 4.6 Profile
1. Click "Profile" in header
2. Should see your onboarding information
3. Click "Update Profile" to re-run onboarding

### 4.7 Upgrade (Optional)
1. Click "Upgrade" in header
2. Should see upgrade page
3. (Stripe integration requires Stripe keys to be configured)

## Step 5: Test Edge Cases

### Test Empty Recommendations
1. Create a new user
2. Complete onboarding with very specific criteria
3. Check if recommendations still work

### Test Invalid Auth
1. Try accessing `/recommendations` without token
2. Should get 401 Unauthorized

### Test Duplicate Email
1. Try signing up with same email twice
2. Should get error message

### Test Invalid Onboarding
1. Try submitting onboarding with missing required fields
2. Should see validation errors

## Step 6: Database Verification

### Check Tables

```bash
psql -U postgres -d readar
```

```sql
-- Check users
SELECT id, email, subscription_status FROM users;

-- Check onboarding profiles
SELECT id, user_id, full_name, business_stage FROM onboarding_profiles;

-- Check books
SELECT COUNT(*) FROM books;
SELECT title, author_name FROM books LIMIT 5;

-- Check recommendations
SELECT COUNT(*) FROM recommendation_sessions;

-- Check user book interactions
SELECT * FROM user_book_interactions;
```

## Troubleshooting

### Backend won't start
- Check PostgreSQL is running: `pg_isready`
- Verify DATABASE_URL in .env
- Check port 8000 is not in use

### Frontend won't start
- Check Node.js version: `node --version` (should be 18+)
- Delete `node_modules` and run `npm install` again
- Check port 5173 is not in use

### Database connection errors
- Verify PostgreSQL credentials
- Check database exists: `psql -l | grep readar`
- Try connecting manually: `psql -U postgres -d readar`

### CORS errors
- Make sure backend CORS_ORIGINS includes frontend URL
- Restart backend after changing .env

### No recommendations
- Verify onboarding profile exists
- Check books are seeded: `SELECT COUNT(*) FROM books;`
- Check recommendation engine logic in `app/services/recommendation_engine.py`

### Migration errors
- Make sure you're in the backend directory
- Check alembic.ini has correct DATABASE_URL
- Try: `alembic downgrade -1` then `alembic upgrade head`

## Quick Test Script

Save this as `test_api.sh`:

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

echo "1. Health check..."
curl -s $BASE_URL/health | jq

echo -e "\n2. Sign up..."
SIGNUP_RESPONSE=$(curl -s -X POST $BASE_URL/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test'$(date +%s)'@example.com", "password": "test123456"}')

TOKEN=$(echo $SIGNUP_RESPONSE | jq -r '.access_token')
echo "Token: ${TOKEN:0:20}..."

echo -e "\n3. Get current user..."
curl -s $BASE_URL/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq

echo -e "\n4. Get books..."
curl -s "$BASE_URL/books?limit=3" | jq '.[0] | {title, author_name}'

echo -e "\n5. Complete onboarding..."
curl -s -X POST $BASE_URL/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "business_model": "SaaS",
    "business_stage": "pre-revenue",
    "biggest_challenge": "Getting customers"
  }' | jq '{id, business_stage}'

echo -e "\n6. Get recommendations..."
curl -s -X POST $BASE_URL/recommendations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_results": 3}' | jq '.[0] | {title, score}'

echo -e "\n✅ All tests passed!"
```

Make it executable and run:
```bash
chmod +x test_api.sh
./test_api.sh
```

## Next Steps

Once basic testing passes:
1. Test with multiple users
2. Test recommendation algorithm with different profiles
3. Test Stripe integration (requires Stripe test keys)
4. Test error handling and edge cases
5. Load test with multiple concurrent requests

