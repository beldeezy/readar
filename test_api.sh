#!/bin/bash

# Quick API test script for Readar
# Requires: curl, jq (optional but recommended)

BASE_URL="http://localhost:8000"

echo "🧪 Testing Readar API..."
echo ""

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not found. Install for better output: brew install jq"
    JQ_CMD="cat"
else
    JQ_CMD="jq"
fi

# 1. Health check
echo "1️⃣  Health check..."
HEALTH=$(curl -s $BASE_URL/health)
if echo "$HEALTH" | grep -q "ok"; then
    echo "   ✅ Backend is running"
else
    echo "   ❌ Backend not responding"
    exit 1
fi

# 2. Sign up
echo ""
echo "2️⃣  Signing up new user..."
TIMESTAMP=$(date +%s)
SIGNUP_RESPONSE=$(curl -s -X POST $BASE_URL/auth/signup \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"test${TIMESTAMP}@example.com\", \"password\": \"test123456\"}")

TOKEN=$(echo "$SIGNUP_RESPONSE" | $JQ_CMD -r '.access_token // empty')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    echo "   ❌ Signup failed"
    echo "$SIGNUP_RESPONSE" | $JQ_CMD
    exit 1
fi

echo "   ✅ User created, token: ${TOKEN:0:30}..."

# 3. Get current user
echo ""
echo "3️⃣  Getting current user..."
USER_RESPONSE=$(curl -s $BASE_URL/auth/me \
  -H "Authorization: Bearer $TOKEN")
USER_EMAIL=$(echo "$USER_RESPONSE" | $JQ_CMD -r '.email // empty')

if [ -n "$USER_EMAIL" ]; then
    echo "   ✅ User: $USER_EMAIL"
else
    echo "   ❌ Failed to get user"
    exit 1
fi

# 4. Get books
echo ""
echo "4️⃣  Fetching books..."
BOOKS_RESPONSE=$(curl -s "$BASE_URL/books?limit=3")
BOOK_COUNT=$(echo "$BOOKS_RESPONSE" | $JQ_CMD 'length')

if [ "$BOOK_COUNT" -gt 0 ]; then
    FIRST_BOOK=$(echo "$BOOKS_RESPONSE" | $JQ_CMD -r '.[0].title // "N/A"')
    echo "   ✅ Found $BOOK_COUNT books (e.g., $FIRST_BOOK)"
else
    echo "   ⚠️  No books found. Run seed script: python -m app.scripts.seed_books"
fi

# 5. Complete onboarding
echo ""
echo "5️⃣  Completing onboarding..."
ONBOARDING_RESPONSE=$(curl -s -X POST $BASE_URL/onboarding \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Test User",
    "business_model": "SaaS",
    "business_stage": "pre-revenue",
    "biggest_challenge": "Getting my first customers",
    "areas_of_business": ["product", "marketing"]
  }')

ONBOARDING_ID=$(echo "$ONBOARDING_RESPONSE" | $JQ_CMD -r '.id // empty')

if [ -n "$ONBOARDING_ID" ]; then
    echo "   ✅ Onboarding completed"
else
    echo "   ❌ Onboarding failed"
    echo "$ONBOARDING_RESPONSE" | $JQ_CMD
    exit 1
fi

# 6. Get recommendations
echo ""
echo "6️⃣  Getting recommendations..."
RECS_RESPONSE=$(curl -s -X POST $BASE_URL/recommendations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_results": 3}')

REC_COUNT=$(echo "$RECS_RESPONSE" | $JQ_CMD 'length')

if [ "$REC_COUNT" -gt 0 ]; then
    FIRST_REC=$(echo "$RECS_RESPONSE" | $JQ_CMD -r '.[0].title // "N/A"')
    FIRST_SCORE=$(echo "$RECS_RESPONSE" | $JQ_CMD -r '.[0].score // "N/A"')
    echo "   ✅ Got $REC_COUNT recommendations"
    echo "      Top recommendation: $FIRST_REC (score: $FIRST_SCORE)"
else
    echo "   ⚠️  No recommendations (may need more books or different profile)"
fi

# 7. Mark book as interested
if [ "$REC_COUNT" -gt 0 ]; then
    echo ""
    echo "7️⃣  Marking book as interested..."
    BOOK_ID=$(echo "$RECS_RESPONSE" | $JQ_CMD -r '.[0].book_id')
    
    INTERACTION_RESPONSE=$(curl -s -X POST $BASE_URL/user-books \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"book_id\": \"$BOOK_ID\", \"status\": \"interesting\"}")
    
    INTERACTION_ID=$(echo "$INTERACTION_RESPONSE" | $JQ_CMD -r '.id // empty')
    
    if [ -n "$INTERACTION_ID" ]; then
        echo "   ✅ Book marked as interested"
    else
        echo "   ⚠️  Failed to mark book"
    fi
fi

echo ""
echo "✅ All API tests completed!"
echo ""
echo "💡 Next steps:"
echo "   - Test the frontend at http://localhost:5173"
echo "   - Check API docs at http://localhost:8000/docs"
echo "   - Review database: psql -d readar"

