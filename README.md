# Harish Critical Care Classes — Mock Test Platform

Full-stack registration, payments (Razorpay), student dashboard (videos, quizzes), and admin panel.

## Structure

| Folder | Stack |
|--------|--------|
| `backend/` | FastAPI + SQLAlchemy |
| `critical-pulse-hub-main/` | React + Vite + TypeScript |

## Setup

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # edit DB, Razorpay, SMTP
uvicorn app.main:app --reload
```

### Frontend

```bash
cd critical-pulse-hub-main
npm install
# create .env with VITE_API_URL=http://127.0.0.1:8000
npm run dev
```

## Notes

- Do not commit `.env` files (API keys, SMTP, Razorpay secrets).
- `backend/health/` is a local virtualenv and is gitignored.
