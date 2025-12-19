# Readar - Book Recommendations for Entrepreneurs

Readar is a web app that helps entrepreneurs quickly find the best next book to read based on their stage, business model, and current challenges.

## Project Structure

```
readar-v1/
├── backend/          # Python FastAPI backend
│   ├── app/
│   │   ├── core/     # Configuration and security
│   │   ├── routers/  # API route handlers
│   │   ├── schemas/  # Pydantic models
│   │   ├── models.py # SQLAlchemy models
│   │   ├── services/ # Business logic
│   │   └── data/     # Seed data
│   ├── alembic/      # Database migrations
│   └── requirements.txt
└── frontend/         # React TypeScript frontend
    └── src/
        ├── api/      # API client
        ├── components/
        ├── pages/
        └── contexts/
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 12+
- Stripe account (for payments)

## Local Development

### Backend (FastAPI)

From the repo root:

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Frontend (Vite)

From the repo root:

```bash
cd frontend
npm install
npm run dev
```

### Required Environment Variables

**backend/.env**

```
DATABASE_URL=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_JWT_SECRET=... (Supabase Project Settings → API → JWT Secret)
SUPABASE_JWT_AUD=authenticated (optional; defaults to authenticated)
ADMIN_EMAIL_ALLOWLIST=email1@example.com,email2@example.com (optional)
DEBUG=true (optional)
```

**frontend/.env.local**

```
VITE_API_BASE_URL=http://localhost:8000/api
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

**Notes:**
- Do **not** include actual secret values.
- Keep it concise.

## Local Setup

### Quick Start

1. **Create backend environment file:**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your DATABASE_URL and other settings
   ```

2. **Create frontend environment file:**
   ```bash
   cp frontend/.env.example frontend/.env.local
   # Edit frontend/.env.local with your Supabase credentials
   ```

3. **Run database migrations:**
   ```bash
   cd backend
   source venv/bin/activate
   alembic upgrade head
   ```

4. **Start backend:**
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload
   ```

5. **Start frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

## Backend Setup

### 1. Install Dependencies

```bash
cd ~/readar-v1/backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in `readar-v1/backend/` (copy from `.env.example`):

```bash
cp backend/.env.example backend/.env
```

Then edit `backend/.env` with your settings:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/readar
ENV=local
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Supabase Auth API (for magic link authentication)
SUPABASE_URL="https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_ANON_KEY="YOUR_SUPABASE_ANON_PUBLIC_KEY"

# Admin access control (comma-separated list of admin emails)
ADMIN_EMAIL_ALLOWLIST=michael@example.com,other@example.com

# Stripe (optional for V1)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]

ENVIRONMENT=development
DEBUG=true
```

### 3. Set Up Database

```bash
# Create database
createdb readar

# Run migrations
cd ~/readar-v1/backend
source venv/bin/activate
alembic upgrade head
```

### 4. Seed Books

```bash
cd ~/readar-v1/backend
python -m app.scripts.seed_books
```

### 5. Run Backend

```bash
cd ~/readar-v1/backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://127.0.0.1:8000` (or `http://localhost:8000`)
API documentation at `http://127.0.0.1:8000/docs`

## Frontend Setup

### 1. Install Dependencies

```bash
cd ~/readar-v1/frontend
npm install
```

### 2. Configure Environment Variables

Create a `.env.local` file in `readar-v1/frontend/` (copy from `.env.example`):

```bash
cp frontend/.env.example frontend/.env.local
```

Then edit `frontend/.env.local` with your settings:

```env
VITE_API_BASE_URL="http://127.0.0.1:8000"
VITE_STRIPE_PRICE_ID=price_...  # Optional

# Supabase (for magic link authentication - required)
VITE_SUPABASE_URL="https://YOUR_PROJECT_REF.supabase.co"
VITE_SUPABASE_ANON_KEY="YOUR_ANON_PUBLIC_KEY"
```

**Note:** The frontend automatically appends `/api` to `VITE_API_BASE_URL` if not already present. So `http://127.0.0.1:8000` becomes `http://127.0.0.1:8000/api` for API calls.

**Important:** Use `127.0.0.1` instead of `localhost` for IPv4 consistency and to avoid DNS resolution issues.

**Note:** Get your Supabase credentials from your Supabase project dashboard:
1. Go to Project Settings → API
2. Copy the "Project URL" as `VITE_SUPABASE_URL`
3. Copy the "anon public" key as `VITE_SUPABASE_ANON_KEY`

**Important:** Configure Supabase Authentication settings:
1. Go to Authentication → URL Configuration
2. Set **Site URL** to: `http://localhost:5173`
3. Add **Redirect URLs**: `http://localhost:5173/auth/callback`
4. Save changes

This ensures magic link authentication works correctly in development.

### 3. Run Frontend

```bash
cd ~/readar-v1/frontend
npm run dev
```

The app will be available at `http://localhost:5173`

**Important:** After changing environment variables in `frontend/.env.local`, you must restart Vite:

```bash
# Stop Vite (Ctrl+C)
# Then restart:
npm run dev
```

Environment variables will not load until Vite restarts. You can verify your environment variables are loaded by visiting `http://localhost:5173/env`.

## Database Migrations

### Create a new migration

```bash
cd ~/readar-v1/backend
alembic revision --autogenerate -m "description"
```

### Apply migrations

```bash
cd ~/readar-v1/backend
alembic upgrade head
```

### Rollback migration

```bash
cd ~/readar-v1/backend
alembic downgrade -1
```

### Fixing Alembic Migration State Issues

If you encounter errors about missing revisions or multiple heads:

**Symptoms:**
- `alembic_version` table references a revision that doesn't exist locally (e.g., `80a813719b89`)
- Multiple Alembic heads exist
- Database missing tables that code expects (e.g., `user_book_status`)

**Solution:**

1. **Check current DB revision:**
   ```bash
   psql $DATABASE_URL -c "SELECT * FROM alembic_version;"
   ```

2. **If DB has invalid revision, stamp to a known good revision:**
   ```bash
   # Option 1: If event_logs table exists, stamp to that migration
   psql $DATABASE_URL -c "UPDATE alembic_version SET version_num='add_event_logs_table';"
   
   # Option 2: If auth fields exist, stamp to the merge migration
   psql $DATABASE_URL -c "UPDATE alembic_version SET version_num='9b0a1aada2ec';"
   ```

3. **Apply all migrations:**
   ```bash
   cd ~/readar-v1/backend
   source venv/bin/activate
   alembic upgrade head
   ```

4. **If multiple heads exist, create a merge migration:**
   ```bash
   # This should already exist in the repo, but if needed:
   alembic merge -m "merge heads" <head1> <head2>
   alembic upgrade head
   ```

**Note:** The recommendation engine includes defensive code to handle missing `user_book_status` table gracefully. If the table is missing, recommendations will still work but without status-based filtering.

## API Endpoints

### Auth
- `POST /auth/signup` - Create account
- `POST /auth/login` - Login
- `GET /auth/me` - Get current user

### Onboarding
- `POST /onboarding` - Create/update profile
- `GET /onboarding` - Get profile

### Books
- `GET /books` - List books (with filters)
- `GET /books/{id}` - Get book details
- `POST /books/seed/debug` - Seed books (dev only)

### Recommendations
- `GET /recommendations` - Get personalized recommendations (requires auth)
- `POST /recommendations` - Get personalized recommendations (requires auth, backward compatibility)
- `POST /recommendations/preview` - Get preview recommendations from onboarding payload (no auth required)

### User Books
- `POST /user-books` - Create/update interaction
- `GET /user-books` - List interactions
- `GET /user-books/{book_id}` - Get interaction

### Billing
- `POST /billing/create-checkout-session` - Create Stripe checkout
- `POST /billing/webhook` - Stripe webhook handler

## Testing the API

### Sign Up

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

### Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

Save the `access_token` from the response.

### Get Recommendations

```bash
curl -X POST http://localhost:8000/recommendations \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_results": 10}'
```

## Authentication Flow (No Login Wall Until Recommendations)

Readar now allows users to complete onboarding and see preview recommendations before logging in. The login requirement is only enforced when viewing final recommendations.

### Flow Overview

1. **Landing & Onboarding (Public)**
   - Users can access `/`, `/onboarding`, and `/recommendations/loading` without authentication
   - Onboarding data is saved to `localStorage` under the key `readar_pending_onboarding`

2. **Preview Recommendations (Public)**
   - After completing onboarding, users are redirected to `/recommendations/loading`
   - The loading page calls `POST /recommendations/preview` (no auth required) with the onboarding payload
   - Preview recommendations are stored in `localStorage` under the key `readar_preview_recs`
   - User is then redirected to `/login?next=/recommendations`

3. **Login & Persistence**
   - After successful login via Supabase magic link, `AuthCallbackPage`:
     - Checks for `readar_pending_onboarding` in localStorage
     - If found, persists it to the backend via `POST /onboarding`
     - Clears the pending onboarding from localStorage
     - Redirects to the `next` param (default: `/recommendations`)

4. **Final Recommendations (Protected)**
   - `/recommendations` requires authentication
   - On mount, it tries to fetch from `GET /recommendations` (authenticated)
   - If backend is unreachable or errors, it falls back to `readar_preview_recs` from localStorage
   - Preview recs are cleared after use

### localStorage Keys

- `readar_pending_onboarding`: Stores onboarding form data (JSON string of `OnboardingPayload`)
- `readar_preview_recs`: Stores preview recommendations (JSON string of `RecommendationItem[]`)

### Backend Preview Endpoint

The `POST /recommendations/preview` endpoint:
- Does NOT require authentication
- Accepts an `OnboardingPayload` in the request body
- Generates recommendations using the same scoring logic as authenticated recommendations
- Does NOT create or mutate user rows
- Falls back to generic recommendations if scoring fails

## Deployment

### Backend

1. Set up PostgreSQL database (Supabase, Railway, Neon, etc.)
2. Set environment variables on your hosting platform
3. Deploy to Render/Railway/Fly.io/Heroku
4. Configure Stripe webhook URL: `https://your-backend.com/billing/webhook`

### Frontend

1. Build the app: `npm run build`
2. Deploy to Vercel/Netlify
3. Set environment variables in deployment settings

## Environment Variables Summary

### Backend
- `DATABASE_URL` - PostgreSQL connection string
- `SUPABASE_URL` - Supabase project URL (required for token validation)
- `SUPABASE_ANON_KEY` - Supabase anonymous/public key (required for token validation)
- `ADMIN_EMAIL_ALLOWLIST` - Comma-separated list of admin emails (e.g., `admin@example.com,other@example.com`)
- `JWT_SECRET_KEY` - Secret for JWT tokens (legacy, may not be used with Supabase)
- `STRIPE_SECRET_KEY` - Stripe secret key (optional)
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook secret (optional)
- `CORS_ORIGINS` - Allowed CORS origins

### Frontend
- `VITE_API_BASE_URL` - Backend API URL
- `VITE_STRIPE_PRICE_ID` - Stripe price ID for subscriptions (optional)
- `VITE_SUPABASE_URL` - Supabase project URL (required for magic link authentication)
- `VITE_SUPABASE_ANON_KEY` - Supabase anonymous/public key (required for magic link authentication)

## Development Notes

- The backend uses FastAPI with automatic API documentation at `/docs`
- The frontend uses React with TypeScript and Vite
- Authentication uses JWT tokens stored in localStorage
- Book recommendations use a scoring algorithm based on business stage, functional tags, and theme tags
- Stripe integration is minimal for V1 - basic checkout flow

## Troubleshooting

### Database Connection Issues
- Verify PostgreSQL is running
- Check `DATABASE_URL` format: `postgresql://user:password@host:port/dbname`
- Ensure database exists: `createdb readar`

### Migration Issues
- Make sure you're in the backend directory when running alembic
- Check that models are imported in `alembic/env.py`

### CORS Issues
- Add your frontend URL to `CORS_ORIGINS` in backend config
- Restart backend after changing CORS settings

### Stripe Issues
- Use test mode keys for development
- Configure webhook endpoint in Stripe dashboard
- Use Stripe CLI for local webhook testing: `stripe listen --forward-to localhost:8000/billing/webhook`

## License

MIT

