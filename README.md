# ForgettingCurve

A local research MVP for measuring an individual's forgetting curve using Korean-to-English vocabulary recall.

The system will present Korean vocabulary prompts, collect English recall responses, preserve item-level raw data, and eventually fit an individual retention curve:

```text
R(t) = exp(-((t / T) ** c))
```

For the MVP, the backend and frontend are intentionally minimal. Experiment pages, database tables, authentication, vocabulary data, and curve fitting are not implemented yet.

## Directory Structure

```text
.
├── backend/              # FastAPI API managed with uv
│   ├── app/
│   │   └── main.py       # Minimal FastAPI app
│   ├── tests/
│   │   └── test_health.py
│   ├── .python-version   # Pins Python 3.12
│   └── pyproject.toml
├── docs/
│   └── architecture.md   # Planned architecture notes
├── frontend/             # Next.js TypeScript App Router app
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── eslint.config.mjs
│   ├── next.config.ts
│   ├── package.json
│   └── tsconfig.json
├── .gitignore
└── README.md
```

## macOS Setup

Install Python 3.12 and uv:

```sh
brew install python@3.12 uv
```

Install backend dependencies:

```sh
cd backend
uv sync
```

Install frontend dependencies:

```sh
cd frontend
npm install
```

## Run Backend

```sh
cd backend
uv run uvicorn app.main:app --reload
```

The health endpoint is available at:

```text
http://127.0.0.1:8000/health
```

## Run Frontend

```sh
cd frontend
npm run dev
```

The frontend is available at:

```text
http://localhost:3000
```

## Run Backend Tests

```sh
cd backend
uv run pytest
```
