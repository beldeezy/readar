# Onboarding Questions

This document contains all onboarding questions for the Readar chat interface. Questions are designed with 5th-grade reading level in active voice.

## Question Structure

Each question includes:
- **ID**: Database field name
- **Question**: Conversational text shown to user
- **Type**: Input type (text, select, multi-select, textarea, book-calibration, file-upload)
- **Required**: Whether the question must be answered
- **Options**: Available choices (for select/multi-select)
- **Order**: Sequence in the chat flow

---

## Questions List

### 1. Entrepreneur Status
- **ID**: `entrepreneur_status`
- **Question**: "Are you working on your business full-time, part-time, or just thinking about it?"
- **Type**: select
- **Required**: No
- **Options**:
  - "Just thinking about it" → `considering`
  - "Part-time (I have another job)" → `part_time`
  - "Full-time (this is my main focus)" → `full_time`
- **Order**: 1

### 2. Economic Sector
- **ID**: `economic_sector`
- **Question**: "What type of work does your business do?"
- **Type**: select
- **Required**: Yes
- **Options**:
  - "Making physical things (farming, mining, manufacturing)" → `primary`
  - "Building things (construction, utilities)" → `secondary`
  - "Selling things or services (retail, hospitality)" → `tertiary`
  - "Information and knowledge (tech, finance, consulting)" → `quaternary`
  - "People services (healthcare, education, government)" → `quinary`
- **Order**: 2
- **Notes**: This determines which industries show in the next question

### 3. Industry
- **ID**: `industry`
- **Question**: "Which industry best describes your business?"
- **Type**: select
- **Required**: Yes
- **Options**: Filtered based on economic_sector selection
  - **Primary Sector**:
    - "Agriculture & Food" → `agriculture`
    - "Energy & Natural Resources" → `energy`
  - **Secondary Sector**:
    - "Manufacturing & Production" → `manufacturing`
    - "Construction & Real Estate" → `construction`
  - **Tertiary Sector**:
    - "Retail & E-commerce" → `retail`
    - "Hospitality & Tourism" → `hospitality`
    - "Transportation & Logistics" → `transportation`
  - **Quaternary Sector**:
    - "Technology & Software" → `technology`
    - "Finance & Insurance" → `finance`
    - "Consulting & Professional Services" → `consulting`
  - **Quinary Sector**:
    - "Healthcare & Wellness" → `healthcare`
    - "Education & Training" → `education`
    - "Government & Nonprofit" → `government`
- **Order**: 3

### 4. Business Model
- **ID**: `business_model`
- **Question**: "How does your business make money? (Pick all that apply)"
- **Type**: multi-select
- **Required**: Yes
- **Options**:
  - "Selling products" → `product`
  - "Providing services" → `service`
  - "Monthly subscriptions" → `subscription`
  - "Showing ads" → `advertising`
  - "Connecting buyers and sellers" → `marketplace`
  - "Getting paid when people buy through my links" → `affiliate`
  - "Selling expensive items or courses" → `direct_sales`
  - "Licensing my ideas or brand" → `licensing`
  - "Running a franchise" → `franchise`
  - "A mix of different ways" → `hybrid`
- **Order**: 4

### 5. Business Stage
- **ID**: `business_stage`
- **Question**: "What stage is your business at right now?"
- **Type**: select
- **Required**: Yes
- **Options**:
  - "Just an idea (planning stage)" → `idea`
  - "Started but not making money yet" → `pre-revenue`
  - "Making some money" → `early-revenue`
  - "Growing and scaling up" → `scaling`
- **Order**: 5

### 6. Current Gross Revenue
- **ID**: `current_gross_revenue`
- **Question**: "How much money does your business make each year?"
- **Type**: select
- **Required**: No
- **Options**:
  - "Not making money yet" → `pre-revenue`
  - "Less than $10,000" → `under_10k`
  - "$10,000 - $50,000" → `10k_50k`
  - "$50,000 - $100,000" → `50k_100k`
  - "$100,000 - $250,000" → `100k_250k`
  - "$250,000 - $500,000" → `250k_500k`
  - "$500,000 - $1 million" → `500k_1m`
  - "$1 million - $5 million" → `1m_5m`
  - "$5 million - $10 million" → `5m_10m`
  - "$10 million - $100 million" → `10m_100m`
  - "More than $100 million" → `100m_plus`
- **Order**: 6
- **Condition**: Only show if business_stage is NOT "idea"

### 7. Organization Size
- **ID**: `org_size`
- **Question**: "How many people work in your business? (Including you)"
- **Type**: text
- **Required**: No
- **Options**: N/A (free text input, expects number or range like "1", "5-10", etc.)
- **Order**: 7

### 8. Business Experience
- **ID**: `business_experience`
- **Question**: "Tell me about your business experience so far. What have you done? What have you learned?"
- **Type**: textarea
- **Required**: No
- **Options**: N/A (free text)
- **Order**: 8

### 9. Areas of Business Focus
- **ID**: `areas_of_business`
- **Question**: "Which parts of your business do you spend the most time on? (Pick all that apply)"
- **Type**: multi-select
- **Required**: No
- **Options**:
  - "Everything (I wear all the hats!)" → `everything`
  - "Building the product or service" → `product`
  - "Marketing and getting customers" → `marketing`
  - "Taking care of customers" → `customer_success`
  - "Managing money and finances" → `finance`
  - "Running day-to-day operations" → `operations`
  - "Managing people and hiring" → `people`
  - "Technology and systems" → `technology`
  - "Something else" → `other`
- **Order**: 9

### 10. Vision (6-12 months)
- **ID**: `vision_6_12_months`
- **Question**: "Where do you want your business to be in 6-12 months?"
- **Type**: textarea
- **Required**: No
- **Options**: N/A (free text)
- **Order**: 10

### 11. Biggest Challenge
- **ID**: `biggest_challenge`
- **Question**: "What's the biggest challenge holding you back right now?"
- **Type**: textarea
- **Required**: Yes
- **Options**: N/A (free text)
- **Order**: 11
- **Notes**: Consolidated from "biggest_challenge" and "blockers" fields

### 12. Book Calibration
- **ID**: `book_preferences`
- **Question**: "Here are 6 popular business books. Tell me which ones you like! (Pick at least 4)"
- **Type**: book-calibration
- **Required**: Yes (minimum 4 selections)
- **Options**: User selects status for each book:
  - "Read it and loved it" → `read_liked`
  - "Read it but didn't like it" → `read_disliked`
  - "Want to read it" → `interested`
  - "Not interested" → `not_interested`
- **Books**:
  1. The Lean Startup (Eric Ries)
  2. Zero to One (Peter Thiel)
  3. The E-Myth Revisited (Michael Gerber)
  4. The Psychology of Money (Morgan Housel)
  5. Deep Work (Cal Newport)
  6. Atomic Habits (James Clear)
- **Order**: 12

### 13. Reading History Upload
- **ID**: `reading_history_csv`
- **Question**: "Do you use Goodreads to track your reading? You can upload your reading history to help me recommend better books!"
- **Type**: file-upload
- **Required**: No
- **Options**:
  - "Upload CSV file" (button trigger)
  - "Skip for now" (continue without uploading)
- **Order**: 13
- **Notes**: Accepts CSV export from Goodreads

---

## Progress Calculation

**Total Questions**: 13
**Required Questions**: 6 (economic_sector, industry, business_model, business_stage, biggest_challenge, book_calibration)

**Progress Formula**:
```
progress = (answered_questions / total_questions) * 100
```

**Progress Tracking**:
- Each answered question (including optional ones) increases progress
- Book calibration counts as 1 question once 4+ books are rated
- File upload counts when file is successfully uploaded OR user skips

---

## Removed Questions (Simplified)

The following questions were removed from the original onboarding:
- **Full Name**: Removed to reduce friction
- **Location**: Removed to reduce friction
- **Age**: Not in original flow, remains removed
- **Occupation**: Not in original flow, remains removed
- **Is Student**: Not in original flow, remains removed

## Consolidated Fields

- **biggest_challenge + blockers**: Merged into single `biggest_challenge` field (they were duplicates)

---

## Backend Database Fields

### OnboardingProfile Model

| Field | Type | Required | Question # |
|-------|------|----------|------------|
| entrepreneur_status | String | No | 1 |
| economic_sector | String | Yes | 2 |
| industry | String | Yes | 3 |
| business_model | String | Yes | 4 |
| business_stage | Enum | Yes | 5 |
| current_gross_revenue | String | No | 6 |
| org_size | String | No | 7 |
| business_experience | Text | No | 8 |
| areas_of_business | Array[String] | No | 9 |
| vision_6_12_months | Text | No | 10 |
| biggest_challenge | Text | Yes | 11 |
| (book_preferences) | Via UserBookInteraction | Yes | 12 |
| (reading_history) | Via CSV import | No | 13 |

**Deprecated Fields** (no longer used):
- `full_name`
- `location`
- `blockers` (use `biggest_challenge` instead)

---

## Chat Interface Notes

### Conversational Flow
- Questions appear one at a time
- Bot asks question → User responds → Bot acknowledges → Next question
- Use encouraging, friendly language
- Keep messages short and clear

### Input Types by Question
- **Simple choice**: Radio buttons or button group (Q1, Q2, Q3, Q5, Q6)
- **Multiple choice**: Checkboxes or tag selection (Q4, Q9)
- **Short text**: Single-line input (Q7)
- **Long text**: Multi-line textarea (Q8, Q10, Q11)
- **Book grid**: Compact book list with status buttons (Q12)
- **File upload**: Upload button with drag-drop (Q13)

### Save Strategy
Save incrementally after each question is answered. This provides:
- Better UX (no lost progress)
- Real-time validation
- Ability to resume later

### Error Handling
- If a save fails, show inline error
- Allow user to retry or skip
- Don't block progression for optional questions
