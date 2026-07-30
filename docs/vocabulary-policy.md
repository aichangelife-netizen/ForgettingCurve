# Vocabulary Policy

The project uses one canonical English answer for each Korean vocabulary item.

## Exact Answer Checking

Both submitted and canonical answers are normalized with only:

1. Remove leading whitespace.
2. Remove trailing whitespace.
3. Compare with Python `casefold()`.

The checker does not collapse internal whitespace, remove punctuation, accept synonyms, accept alternative answers, use fuzzy matching, correct spelling, use stemming or lemmatization, or use an LLM.

Examples:

- `" Memory "` matches `"memory"`.
- `"MEMORY"` matches `"memory"`.
- `"mem ory"` does not match `"memory"`.
- `"memories"` does not match `"memory"`.
- `"recollection"` does not match `"memory"`.
- `""` is a valid submitted answer, but it is incorrect for any nonblank canonical answer.

Reusable functions live in `backend/app/services/answer_scoring.py`:

- `normalize_answer(answer: str) -> str`
- `check_answer(user_answer: str, canonical_answer: str) -> bool`

Stage 4 learning attempts store the original submitted answer and the normalized submitted answer. A blank submitted answer is stored and scored incorrect for any nonblank canonical answer. The canonical answer is returned only after submission as learning feedback.

## Demonstration Source Data

The reviewable source file is `backend/data/vocabulary.json`.

It contains 30 demonstration Korean-English vocabulary items for development and schema/API testing. These items are not final research materials.

Each row contains:

- `korean`
- `english_answer`

The source file intentionally excludes alternative answers, difficulty, part of speech, accepted answers, and obvious English loanwords.

## Import Behavior

Run the import command:

```sh
cd backend
uv run python scripts/import_vocabulary.py
```

Running the import repeatedly is idempotent:

- New Korean words are inserted.
- Existing rows are skipped by default.
- Existing canonical English answers are updated only with `--update-existing`.
- Inactive existing rows remain inactive.

The command reports inserted, skipped, and updated counts.

Malformed vocabulary source files are rejected for unsupported fields, duplicate Korean words, blank Korean words, blank English answers, non-object rows, and invalid JSON.
