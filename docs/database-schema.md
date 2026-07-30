# Database Schema

Stage 2 establishes the database foundation only. It does not implement API routes, learning logic, random assignment, curve fitting, frontend pages, or vocabulary seed data.

Stage 3 uses this schema for vocabulary import, anonymous participants, draft test-design creation, test-design group creation, and the draft-to-learning transition. It does not require a new database migration.

## Configuration

- Backend migrations are managed by Alembic in `backend/alembic`.
- The default database URL is `sqlite:///./forgetting_curve.sqlite3`.
- Set `FORGETTING_CURVE_DATABASE_URL` to use another SQLite database.
- SQLite foreign keys are enabled for every SQLAlchemy connection with `PRAGMA foreign_keys=ON`.
- Application timestamps are generated as UTC-aware Python `datetime` values.
- Timestamp columns use `DateTime(timezone=True)` in SQLAlchemy.
- `MASTERY_THRESHOLD` is an application constant with value `2` and is not stored in the database.

## Tables

### participants

Stores research participants.

- `id`: integer primary key.
- `participant_code`: required, unique, nonblank.
- `created_at`: UTC timestamp.

### vocabulary_items

Stores Korean vocabulary prompts and their English answers.

- `id`: integer primary key.
- `korean`: required, unique, nonblank.
- `english_answer`: required, nonblank.
- `is_active`: required boolean.
- `created_at`: UTC timestamp.

No difficulty, part of speech, or accepted-answer list is stored in Stage 2.

The Stage 3 demonstration vocabulary source stores exactly one canonical English answer per Korean word. It remains demonstration data, not final research material.

### test_designs

Stores one experimental design for one participant.

- `id`: integer primary key.
- `participant_id`: references `participants.id`.
- `items_per_group`: required, greater than zero.
- `group_count`: required, greater than zero.
- `random_seed`: required integer.
- `status`: one of `draft`, `learning`, `assigning`, `activation_review`, `active`, `completed`, `cancelled`.
- Lifecycle timestamps: `created_at`, `learning_started_at`, `activation_review_started_at`, `activated_at`, `completed_at`.

`required_item_count` is calculated in application code as `items_per_group * group_count`.

A SQLite partial unique index enforces at most one non-terminal design per participant. Non-terminal statuses are `draft`, `learning`, `assigning`, `activation_review`, and `active`.

### test_design_groups

Stores delayed recall interval groups within a design.

- `id`: integer primary key.
- `test_design_id`: references `test_designs.id`.
- `group_index`: starts at 1 and must be greater than zero.
- `interval_seconds`: greater than zero.
- `status`: one of `pending`, `completed`, `cancelled`.
- `completed_at`: nullable UTC timestamp.

The schema enforces unique `group_index` and unique `interval_seconds` inside each design.

### test_design_items

Stores the vocabulary items selected into a design and their initial mastery state.

- `id`: integer primary key.
- `test_design_id`: references `test_designs.id`.
- `vocabulary_item_id`: references `vocabulary_items.id`.
- `attempt_count`, `correct_count`, `consecutive_correct_count`: nonnegative counters.
- `is_mastered`: required boolean.
- `mastered_at`: nullable UTC timestamp.
- `created_at`, `updated_at`: UTC timestamps.

The schema enforces one row per vocabulary item inside a design. It also enforces counter ordering and mastery consistency:

- Mastered rows require `mastered_at` and at least `MASTERY_THRESHOLD` consecutive correct answers.
- Unmastered rows require `mastered_at` to be null and fewer than `MASTERY_THRESHOLD` consecutive correct answers.

### test_assignments

Stores delayed recall assignments.

- `id`: integer primary key.
- `test_design_id`: references `test_designs.id`.
- `test_design_item_id`: references a design item in the same design.
- `test_design_group_id`: references a design group in the same design.
- `assignment_order`: starts at 1 and must be greater than zero.
- `anchor_at`, `scheduled_at`, `completed_at`: nullable UTC timestamps.
- `status`: one of `awaiting_anchor`, `pending`, `completed`, `cancelled`.
- `created_at`: UTC timestamp.

Composite foreign keys guarantee that the assigned item and assigned group both belong to the assignment's design.

The schema does not store `due` or `missed`. An assignment is due when `status = 'pending'` and `scheduled_at <= current UTC time`.

Group accuracy is not stored. Later learning and delayed-recall stages should derive accuracy from raw attempt rows so analyses can be recomputed and audited.

### vocabulary_attempts

Stores raw learning-check and delayed-recall attempts.

- `id`: integer primary key.
- `test_design_item_id`: references `test_design_items.id`.
- `test_assignment_id`: nullable reference to one assignment for delayed recall.
- `attempt_type`: one of `learning_check`, `delayed_recall`.
- `user_answer`: required string; an empty string is valid.
- `normalized_answer`: required string.
- `is_correct`: required boolean.
- `response_time_ms`: nullable, nonnegative integer.
- `attempted_at`: UTC timestamp.
- `actual_retention_seconds`: nullable, nonnegative integer.
- `is_valid_for_fitting`: required boolean.
- `exclusion_reason`: nullable string.

Learning checks cannot reference an assignment, cannot have actual retention seconds, and are never valid for fitting.

Delayed recall attempts must reference an assignment and must have actual retention seconds. A nullable unique constraint on `test_assignment_id` enforces one delayed recall row per assignment while still allowing many learning checks with null assignment IDs.

### curve_models

Stores official fitted curve rows. Rows are append-only by policy.

- `id`: integer primary key.
- `participant_id`: references `participants.id`.
- `trigger_test_design_id`: unique design that triggered the model.
- `version`: positive integer, unique per participant.
- `model_name`: must be `exponential_power`.
- `fit_method`: must be `bernoulli_mle`.
- `T`, `c`: positive floats.
- `log_likelihood`: nullable float.
- `sample_count`: positive integer.
- `complete_time_point_count`: at least 5.
- `converged`: required boolean.
- `data_cutoff_at`, `fitted_at`: UTC timestamps.

A composite foreign key guarantees that the trigger design belongs to the same participant as the curve model.

## Delete Policy

Research records must not be casually deleted.

Restricted deletes:

- `participants` to `test_designs`: `ON DELETE RESTRICT`.
- `participants` to `curve_models`: `ON DELETE RESTRICT`.
- `vocabulary_items` to `test_design_items`: `ON DELETE RESTRICT`.
- `curve_models` to trigger `test_designs`: `ON DELETE RESTRICT`.

Contained design records use `ON DELETE CASCADE`:

- `test_designs` to `test_design_groups`.
- `test_designs` to `test_design_items`.
- `test_designs` to `test_assignments`.
- `test_design_items` to `vocabulary_attempts`.
- `test_assignments` to delayed-recall `vocabulary_attempts`.

This cascade policy supports deleting an unused draft design as one contained unit. Completed designs must never be hard-deleted through application code.

## SQLite Notes

- SQLite enforces the partial unique index for one non-terminal design per participant.
- SQLite allows multiple null values in a nullable unique column, which is used for `vocabulary_attempts.test_assignment_id`.
- SQLite does not preserve timezone metadata in the same way as PostgreSQL. The application must write UTC-aware timestamps and treat loaded timestamps as UTC.
- SQLite check constraints cannot compare values across rows. Workflow rules that depend on state transitions or aggregate completeness remain service-layer responsibilities.

## Service-Layer Responsibilities

The database foundation intentionally leaves several rules for later service code:

- Generate and persist UTC-aware timestamps consistently.
- Prevent hard deletion of completed designs and official curve rows.
- Determine whether pending assignments are due.
- Validate later status transitions and lifecycle timestamp ordering beyond `draft` to `learning`.
- Implement random assignment, learning checks, delayed recall scoring, and curve fitting.
- Decide when a delayed recall attempt is valid for fitting and provide a meaningful `exclusion_reason` when it is not.
