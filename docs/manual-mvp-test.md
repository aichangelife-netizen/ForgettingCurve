# Manual MVP Test

This guide starts from a fresh clone and uses short development intervals. Demonstration vocabulary is for software testing and review only; it is not formal research material.

## Install Dependencies

Install Python 3.12, uv, Node.js, and npm. On macOS with Homebrew:

```sh
brew install python@3.12 uv node
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

## Prepare The Database

Use a local SQLite database that is not committed to Git:

```sh
cd backend
uv run alembic upgrade head
uv run python scripts/import_vocabulary.py
```

The import command loads demonstration Korean-English vocabulary from `backend/data/vocabulary.json`.

## Start The Servers

Start the backend:

```sh
cd backend
uv run uvicorn app.main:app --reload
```

Start the frontend in a separate terminal:

```sh
cd frontend
npm run dev
```

Open:

```text
http://localhost:3000
```

The tracked `frontend/.env.example` shows the optional API URL setting:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Do not commit real `.env` or `.env.local` files.

## Complete A Development Experiment

1. Select `Create New Participant`.
2. On `/experiment`, select `Create New Experiment`.
3. On `/experiment/design`, choose the Development preset:

   ```text
   60, 180, 300, 600, 1200
   ```

4. Confirm `group_count`, `required_item_count`, and the message showing how many vocabulary items must be mastered.
5. Create the draft design, note the stored random seed, and select `Start Learning`.
6. Review study materials. Study mode shows both Korean and canonical English answers and creates no attempts.
7. Begin learning checks. The check prompt shows only Korean before submission.
8. Answer each item until every vocabulary item is mastered with two consecutive correct answers.
9. Select `Initialize Test Groups`.
10. In activation review, review each Korean-English pair and select `I Have Reviewed This Word`. Each click creates that word's own `anchor_at` and `scheduled_at`.
11. Open the delayed-test page. If no test is due, inspect `next_scheduled_at`, wait, and refresh.
12. Submit delayed recalls as they become due. During active delayed testing, the UI shows no correctness and no canonical answer.
13. Open results while the experiment is partial to verify raw retention summaries. Partial groups are labeled partial time points and no provisional curve is shown.
14. Finish all delayed-recall groups.
15. On results, inspect raw group summaries first. Confirm completed groups show completed count, correct count, incorrect count, observed accuracy, and actual-retention statistics.
16. Select `Generate Personal Curve` when eligibility is available.
17. Inspect Personal Curve V1, including observed point markers, fitted predicted line, T, c, sample count, complete time point count, warnings, and fitted timestamp.
18. Complete a later experiment for the same participant.
19. Return to results and confirm the curve history can display Personal Curve V1 and Personal Curve V2.
20. Select V1 after V2 exists and confirm it remains a historical snapshot with its original trigger design and sample count.

## Verification Commands

Backend:

```sh
cd backend
uv sync
uv pip check
uv run pytest
FORGETTING_CURVE_DATABASE_URL=sqlite:////tmp/forgetting_curve_manual_verify.sqlite3 uv run alembic upgrade head
```

Frontend:

```sh
cd frontend
npm install
npm run lint
npm run test
npm run build
```

Repository:

```sh
git status --short --branch
git diff --check
git status --ignored --short
```

No secrets or committed database are required for this scenario.
