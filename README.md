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

## Backend Setup

### 1. Install Dependencies

```bash
cd ~/readar-v1/backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in `readar-v1/backend/`:

```env
DATABASE_URL=postgresql://user:password@localhost/readar
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

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
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
API documentation at `http://localhost:8000/docs`

## Frontend Setup

### 1. Install Dependencies

```bash
cd ~/readar-v1/frontend
npm install
```

### 2. Configure Environment Variables

Create a `.env` file in `readar-v1/frontend/`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_STRIPE_PRICE_ID=price_...  # Optional
```

### 3. Run Frontend

```bash
cd ~/readar-v1/frontend
npm run dev
```

The app will be available at `http://localhost:5173`

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
- `POST /recommendations` - Get recommendations

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
- `JWT_SECRET_KEY` - Secret for JWT tokens
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook secret
- `CORS_ORIGINS` - Allowed CORS origins

### Frontend
- `VITE_API_BASE_URL` - Backend API URL
- `VITE_STRIPE_PRICE_ID` - Stripe price ID for subscriptions

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

