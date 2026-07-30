# ForgettingCurve

A local research MVP for measuring an individual's forgetting curve using Korean-to-English vocabulary recall.

The system presents Korean vocabulary prompts, collects English recall responses, preserves item-level raw data, and fits an official individual retention curve:

```text
R(t) = exp(-((t / T) ** c))
```

For the MVP, Stage 8 adds the complete participant-facing frontend workflow: local anonymous participant resume, design creation, learning, activation review, due delayed recall, raw summaries, official curve generation, Personal Curve V1/V2/V3 visualization, and historical curve selection.

## Directory Structure

```text
.
├── backend/              # FastAPI API managed with uv
│   ├── app/
│   │   ├── api/          # FastAPI API routers
│   │   ├── core/         # Application constants
│   │   ├── db/           # SQLAlchemy models and database setup
│   │   ├── schemas/      # API request and response schemas
│   │   ├── services/     # Business rules and import/scoring services
│   │   └── main.py       # Minimal FastAPI app
│   ├── alembic/          # Database migrations
│   ├── data/
│   │   └── vocabulary.json
│   ├── scripts/
│   │   └── import_vocabulary.py
│   ├── tests/
│   │   ├── test_answer_scoring.py
│   │   ├── test_api_stage3.py
│   │   ├── test_assignment_stage5.py
│   │   ├── test_curve_stage7.py
│   │   ├── test_delayed_recall_stage6.py
│   │   ├── test_learning_stage4.py
│   │   ├── test_database_constraints.py
│   │   ├── test_health.py
│   │   └── test_migrations.py
│   ├── .python-version   # Pins Python 3.12
│   ├── alembic.ini
│   └── pyproject.toml
├── docs/
│   ├── architecture.md   # Planned architecture notes
│   ├── curve-fitting.md
│   ├── database-schema.md
│   ├── frontend-workflow.md
│   └── manual-mvp-test.md
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

Optional frontend API configuration:

```sh
cp .env.example .env.local
```

Do not commit real `.env` or `.env.local` files. When `NEXT_PUBLIC_API_BASE_URL` is absent, the frontend falls back to `http://127.0.0.1:8000`.

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

Frontend routes:

- `/`
- `/experiment`
- `/experiment/design`
- `/experiment/[testDesignId]/learn`
- `/experiment/[testDesignId]/activation`
- `/experiment/[testDesignId]/delayed`
- `/experiment/[testDesignId]/results`

## Run Backend Tests

```sh
cd backend
uv run pytest
```

## Run Frontend Checks

```sh
cd frontend
npm run lint
npm run test
npm run build
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

## Import Demonstration Vocabulary

The source file [backend/data/vocabulary.json](backend/data/vocabulary.json) contains 30 demonstration Korean-English items for development and review. It is not final research material.

```sh
cd backend
uv run python scripts/import_vocabulary.py
```

Use `--update-existing` only when existing canonical English answers should be updated.

## API Documentation

See [docs/api.md](docs/api.md) for API endpoints, [docs/vocabulary-policy.md](docs/vocabulary-policy.md) for exact answer checking rules, [docs/curve-fitting.md](docs/curve-fitting.md) for the official fitting contract, [docs/frontend-workflow.md](docs/frontend-workflow.md) for participant-facing routes, and [docs/manual-mvp-test.md](docs/manual-mvp-test.md) for a manual end-to-end scenario.
