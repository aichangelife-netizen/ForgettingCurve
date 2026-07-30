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

SQLite will be used for local storage. SQLAlchemy will model participants, vocabulary items, sessions, initial mastery trials, delayed retention assignments, and delayed recall trials.

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

Stage 1 contains only the project skeleton:

- Minimal FastAPI app with `GET /health`.
- Basic backend health test.
- Minimal Next.js home page.
- Architecture documentation.

The project does not yet include database tables, vocabulary data, experiment logic, authentication, or curve fitting.
