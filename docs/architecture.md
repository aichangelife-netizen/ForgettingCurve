# ForgettingCurve Architecture

ForgettingCurve is a local research MVP for estimating an individual's forgetting curve from Korean-to-English vocabulary recall.

## Goals

- Present Korean vocabulary prompts and collect English recall responses.
- Allow only initially mastered words to enter delayed retention testing.
- Assign each mastered word to exactly one delayed retention interval.
- Preserve item-level raw data for analysis.
- Use actual elapsed time when estimating retention.
- Eventually fit `R(t) = exp(-((t / T) ** c))` with `b` fixed at `1`.

## Planned Components

### Frontend

The frontend is a Next.js TypeScript application using the App Router. It will provide the local research interface for mastery testing, delayed recall testing, and basic progress review.

### Backend

The backend is a FastAPI application running on Python 3.12. It will own experiment state, validation rules, persistence, and analysis endpoints or scripts.

### Persistence

SQLite is used for local storage. SQLAlchemy 2.x typed ORM models and Alembic migrations define participants, vocabulary items, test designs, delayed retention assignment groups, design items, delayed recall assignments, raw vocabulary attempts, and official curve model rows.

### Analysis

NumPy and SciPy will support offline fitting of the retention curve. Analysis should consume item-level trial records and derive actual elapsed time from stored timestamps.

## Data Flow

1. The frontend requests the next Korean vocabulary prompt.
2. The participant submits an English recall response.
3. The backend records the raw response, score, and timestamps.
4. Correctly answered mastery items become eligible for delayed retention assignment.
5. Each eligible item is assigned to exactly one delayed interval.
6. Delayed recall responses are recorded with actual elapsed time available for later analysis.

## Current Scope

Stage 6 contains the project skeleton, database foundation, early API infrastructure, backend learning workflow, deterministic activation scheduling, and delayed-recall result capture:

- Minimal FastAPI app with `GET /health`.
- Basic backend health test.
- SQLAlchemy models for the research schema.
- Alembic migration management.
- SQLite constraint and migration tests.
- Exact answer normalization and scoring.
- Demonstration vocabulary source import.
- Anonymous participant APIs.
- Draft test-design creation, reading, and group creation APIs.
- Fixed learning-pool initialization with deterministic `learning_pool` seed namespace.
- Study-material, next-check, learning-attempt, and progress APIs.
- Two-consecutive-correct mastery tracking.
- Automatic transition from learning to assigning after all pool items are mastered.
- Deterministic `group_assignment` seed namespace for retention-group assignment.
- Round-robin balanced assignment across retention groups.
- Activation-review APIs with global assignment order.
- Per-item `anchor_at` and calculated `scheduled_at`.
- Automatic transition from activation review to active after all assignments are anchored.
- Derived due delayed-recall retrieval.
- Delayed-recall submission with actual retention seconds.
- Assignment, group, and design completion.
- Raw retention progress, summaries, and participant history.
- Minimal Next.js home page.
- Architecture documentation.

The project does not yet include final research vocabulary, forgetting-curve fitting, curve model creation, authentication, admin pages, participant-facing frontend pages, notifications, or background jobs.
