# ForgettingCurve

A local research MVP for measuring an individual's forgetting curve using Korean-to-English vocabulary recall.

The system will present Korean vocabulary prompts, collect English recall responses, preserve item-level raw data, and eventually fit an individual retention curve:

```text
R(t) = exp(-((t / T) ** c))
```

For the MVP, the backend and frontend are intentionally minimal. Stage 2 adds the SQLite database foundation, Alembic migrations, and database-level integrity tests. Experiment pages, API workflows, vocabulary data, random assignment, learning logic, and curve fitting are not implemented yet.

## Directory Structure

```text
.
├── backend/              # FastAPI API managed with uv
│   ├── app/
│   │   ├── core/         # Application constants
│   │   ├── db/           # SQLAlchemy models and database setup
│   │   └── main.py       # Minimal FastAPI app
│   ├── alembic/          # Database migrations
│   ├── tests/
│   │   ├── test_database_constraints.py
│   │   ├── test_health.py
│   │   └── test_migrations.py
│   ├── .python-version   # Pins Python 3.12
│   ├── alembic.ini
│   └── pyproject.toml
├── docs/
│   ├── architecture.md   # Planned architecture notes
│   └── database-schema.md
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

## Database

The backend uses SQLite with SQLAlchemy 2.x typed ORM models and Alembic migrations. Foreign keys are enabled for every SQLite connection with `PRAGMA foreign_keys=ON`.

By default, local commands use `backend/forgetting_curve.sqlite3`, which is ignored by Git. To target another database, set `FORGETTING_CURVE_DATABASE_URL`.

Run migrations:

```sh
cd backend
uv run alembic upgrade head
```

Run migrations against a temporary database:

```sh
cd backend
FORGETTING_CURVE_DATABASE_URL=sqlite:////tmp/forgetting_curve_stage2.sqlite3 uv run alembic upgrade head
```

See [docs/database-schema.md](docs/database-schema.md) for the schema, delete policy, and SQLite notes.
