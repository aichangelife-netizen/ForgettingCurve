# Database Schema

Stage 2 establishes the database foundation only. It does not implement API routes, learning logic, random assignment, curve fitting, frontend pages, or vocabulary seed data.

Stage 3 uses this schema for vocabulary import, anonymous participants, draft test-design creation, test-design group creation, and the draft-to-learning transition. Stage 4 uses the same schema for fixed learning pools, learning-check attempts, mastery tracking, and automatic transition to assigning. Stage 5 uses it for deterministic group assignment, activation review, per-item `anchor_at`, and delayed-test scheduling. Stage 6 uses it for delayed-recall attempts, actual retention seconds, completed assignments, completed groups, completed designs, and raw retention summaries. Stage 7 uses the existing `curve_models` table for official curve persistence and does not require a new database migration. Stage 9 hardening also does not require a database migration.

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

Starting learning creates the fixed learning pool by inserting exactly `required_item_count` rows into `test_design_items`. The pool is selected from active vocabulary at initialization time and then frozen as persisted rows.

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

Stage 4 uses `updated_at` for round-robin learning checks. Items with no attempts come first; attempted unmastered items move behind other unmastered items when `updated_at` is refreshed.

Learning progress counts mastered items with an explicit conditional count rather than summing the boolean column, so SQLite reports the true mastered-item count consistently.

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

Stage 5 creates assignments after all learning-pool items are mastered. It sorts design items by `id`, shuffles them with a deterministic `group_assignment` seed namespace, and assigns them to groups round-robin in `group_index` order. The `assignment_order` values are globally unique within the design at the service layer and cover `1` through `required_item_count`.

During activation review, each assignment receives a server-generated `anchor_at`. The service calculates `scheduled_at = anchor_at + interval_seconds`. Each assignment can have a different anchor timestamp because activation review may take several minutes.

The schema does not store `due` or `missed`. An assignment is due when `status = 'pending'` and `scheduled_at <= current UTC time`.

Stage 6 changes pending assignments to completed only after a due delayed-recall submission. Late tests remain accepted. The service preserves the original `anchor_at` and `scheduled_at`, stores the server-generated `completed_at`, and calculates actual retention from `attempted_at - anchor_at`.

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

Learning checks cannot reference an assignment, cannot have actual retention seconds, and are never valid for fitting. They are practice data from the initial mastery workflow, not delayed-retention observations.

Delayed recall attempts must reference an assignment and must have actual retention seconds. A nullable unique constraint on `test_assignment_id` enforces one delayed recall row per assignment while still allowing many learning checks with null assignment IDs.

Stage 6 delayed-recall attempts are valid for fitting by default. Stage 7 official curve fitting consumes only valid delayed-recall item rows with positive `actual_retention_seconds`; learning checks, activation review, invalid attempts, and aggregate group percentages are excluded from fitting. Raw summaries calculate group accuracy and retention statistics from item-level delayed-recall rows; they do not store aggregate accuracy.

### curve_models

Stores official fitted curve rows. Rows are append-only by service policy.

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

Stage 7 inserts one row per completed trigger design at most. Versions are assigned as positive integers per participant and displayed as `Personal Curve V1`, `Personal Curve V2`, and so on. Creating a newer version does not update or delete older rows. The service rejects an older trigger design after a later trigger already has a curve, so a version cannot silently include data from beyond its chronological cutoff.

`data_cutoff_at` records the latest included delayed-recall attempt timestamp for the trigger's source dataset. Historical retrieval reconstructs observed points from completed designs through the stored trigger design and recomputes predicted points from the immutable stored `T` and `c`.

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
- SQLite does not provide strong row-level locks. Uniqueness constraints plus transactional revalidation provide practical duplicate-submission protection for the local MVP, while a production multi-user deployment may require PostgreSQL and row locks.

## Service-Layer Responsibilities

The database foundation intentionally leaves several rules for later service code:

- Generate and persist UTC-aware timestamps consistently.
- Prevent hard deletion of completed designs and official curve rows.
- Determine whether pending assignments are due.
- Validate later status transitions and lifecycle timestamp ordering beyond design completion.
- Maintain append-only behavior for completed designs and official curve rows.
- Decide when a delayed recall attempt is valid for fitting and provide a meaningful `exclusion_reason` when it is not.
- Enforce curve-fitting eligibility, chronological trigger order, and transactional duplicate protection.
