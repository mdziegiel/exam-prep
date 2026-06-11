# IT Exam Prep

A polished, self-hosted IT certification exam preparation application for serious lab rats who prefer owning their data instead of renting flashcards from someone else's SaaS pile.

## Supported exams

- MD-102 Microsoft Endpoint Administrator
- AZ-104 Azure Administrator Associate
- CompTIA Network+ N10-009

Each exam ships with a SQLite-backed starter bank of 320 questions mapped to exam objectives. Questions are structured for spaced repetition and can be expanded through manual import, community scraping, and Claude-generated candidates.

## Features

- React + Tailwind dark professional UI
- FastAPI backend with SQLite persistence
- Practice mode with immediate feedback
- Timed exam mode with 90-minute exam simulation
- Passing score display and pass/fail result
- Spaced repetition queue
  - correct answers move further out
  - wrong answers return quickly
  - mastery score tracked per question
- Question flagging for review
- Explanation after every answer
- Objective mapping per question
- Progress dashboard by exam and objective
- Weak area tracking
- Attempt history with scores and dates
- Admin review queue
- Manual JSON question import
- Refresh button for scraper and Claude generation candidates
- Deduplication by normalized question fingerprint
- Single Docker container serving frontend and backend
- Persistent Docker volume for SQLite

## Screenshots

Place screenshots here after deployment:

- `docs/screenshots/dashboard.png`
- `docs/screenshots/practice.png`
- `docs/screenshots/results.png`
- `docs/screenshots/admin-review.png`

## Quickstart

```bash
cp .env.example .env
# Optional: edit .env and add ANTHROPIC_API_KEY for Claude question generation.
docker compose up -d --build
```

Open:

```text
http://localhost:8083
```

Health check:

```bash
curl http://localhost:8083/api/health
```

## Environment

```text
ANTHROPIC_API_KEY=                  # optional, needed for LLM generation
ANTHROPIC_MODEL=claude-sonnet-4-20250514
DATABASE_PATH=/data/exam-prep.sqlite
```

## Data persistence

The compose file creates a named volume:

```text
exam-prep-data:/data
```

The SQLite database lives at:

```text
/data/exam-prep.sqlite
```

## Admin workflow

1. Open Admin.
2. Select an exam.
3. Click `Check for new questions`.
4. Scraper and/or Claude generation creates unverified candidates.
5. Review each question.
6. Approve good items into the active question pool.
7. Reject garbage. There will be garbage. This is the internet.

## Manual import JSON

Paste this shape into the Admin manual import box:

```json
{
  "objective_code": "1.1",
  "question_text": "A company wants to deploy Windows clients with minimal technician interaction. What should the administrator configure?",
  "choices": [
    "Windows Autopilot deployment profile",
    "Manual local installation media",
    "Disable device enrollment",
    "Unmanaged workgroup deployment"
  ],
  "correct_choice": "A",
  "explanation": "Windows Autopilot supports cloud-driven Windows provisioning and maps to MD-102 deployment objectives."
}
```

Manual imports enter the review queue unless marked verified through the API.

## API highlights

- `GET /api/health`
- `GET /api/exams`
- `GET /api/exams/{exam_id}/queue?mode=practice&limit=20`
- `POST /api/answer`
- `POST /api/attempts`
- `GET /api/attempts`
- `GET /api/admin/review`
- `POST /api/admin/questions`
- `POST /api/admin/review/{question_id}`
- `POST /api/admin/refresh`

## Development

Backend:

```bash
cd backend
python3 seed.py
uvicorn main:app --reload --port 8083
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

For production, use Docker. That is the point.

## Notes on sourcing

Community-sourced and generated questions are marked unverified and inactive until approved. The app intentionally keeps a human review gate because blindly trusting scraped exam content is how weak people build liability engines.
