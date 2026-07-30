# API

All API paths are mounted under `/api`. Responses use JSON. Service-layer errors use:

```json
{
  "detail": {
    "code": "machine_readable_code",
    "message": "Human-readable English message."
  }
}
```

The FastAPI app allows local frontend CORS for `http://localhost:3000` and `http://127.0.0.1:3000`. It does not use wildcard origins with credentials.

## Participants

### POST /api/participants

Creates an anonymous participant. The request body is empty. The API does not accept names, email addresses, passwords, or other identifying fields.

The server generates a unique participant code in the format `P-XXXXXXXX`, where the suffix is an uppercase random identifier.

Response:

```json
{
  "id": 1,
  "participant_code": "P-AB12CD34",
  "created_at": "UTC timestamp"
}
```

### GET /api/participants/{participant_id}

Returns a participant by ID.

Missing participants return `404` with code `participant_not_found`.

## Vocabulary Items

### GET /api/vocabulary-items

Returns vocabulary items in stable order.

Query parameters:

- `include_inactive`: optional boolean, defaults to `false`.
- `limit`: optional integer from 1 through 100, defaults to `50`.
- `offset`: optional nonnegative integer, defaults to `0`.

Only active items are returned by default. The response exposes only the fields needed for this stage.

## Test Designs

### POST /api/test-designs

Creates one draft test design and its retention interval groups in one transaction.

Request:

```json
{
  "participant_id": 1,
  "items_per_group": 20,
  "intervals_seconds": [600, 3600, 21600, 86400, 604800],
  "random_seed": 12345
}
```

`random_seed` is optional. When omitted, the server generates and stores one.

The client does not send `group_count`. The server derives `group_count` from `len(intervals_seconds)` so that the stored group count cannot disagree with the supplied intervals.

`required_item_count` is calculated as `items_per_group * group_count` and returned in the API response. It is not stored in the database.

Response:

```json
{
  "id": 1,
  "participant_id": 1,
  "items_per_group": 20,
  "group_count": 5,
  "required_item_count": 100,
  "random_seed": 12345,
  "status": "draft",
  "groups": [
    {
      "id": 1,
      "group_index": 1,
      "interval_seconds": 600,
      "status": "pending",
      "completed_at": null
    }
  ],
  "created_at": "UTC timestamp",
  "learning_started_at": null,
  "activation_review_started_at": null,
  "activated_at": null,
  "completed_at": null
}
```

Validation and conflict responses include:

- `participant_not_found`
- `invalid_items_per_group`
- `empty_intervals`
- `invalid_interval`
- `duplicate_intervals`
- `insufficient_active_vocabulary`
- `unfinished_design_exists`

### GET /api/test-designs/{test_design_id}

Returns design fields, calculated `required_item_count`, ordered groups, and lifecycle timestamps.

Missing designs return `404` with code `test_design_not_found`.

### POST /api/test-designs/{test_design_id}/start-learning

Initializes the fixed learning pool, transitions a design from `draft` to `learning`, and stores `learning_started_at` in one transaction.

The service calculates `required_item_count = items_per_group * group_count`, queries active vocabulary, sorts candidate vocabulary IDs, derives a deterministic local random seed from `SHA256(f"{random_seed}:learning_pool")`, shuffles with a local `random.Random`, and inserts exactly `required_item_count` `test_design_items` in that selected order.

The namespace `learning_pool` keeps this selection independent from future assignment randomization while still using the design's stored `random_seed`.

The persisted `test_design_items` are the frozen learning pool. Later changes to `vocabulary_items.is_active` do not remove items from an initialized design.

Repeated requests or calls for non-draft designs return `409` with code `invalid_design_status_transition`. The timestamp is not silently overwritten.

This endpoint does not create `test_assignments`.

### GET /api/test-designs/{test_design_id}/learning-materials

Returns the explicit study materials for a learning design. It includes canonical answers because this endpoint is for study, not checking.

The response includes `required_item_count`, `mastered_item_count`, `remaining_item_count`, and all fixed-pool items ordered by `test_design_item.id`.

Draft or assigning designs return `409` with code `design_not_learning_for_materials`.

### GET /api/test-designs/{test_design_id}/learning-checks/next

Returns the next unmastered learning check item for a learning design. It returns the Korean prompt, attempt count, and consecutive correct count, but does not return `english_answer` or any normalized canonical answer.

Selection is round-robin:

- Unmastered items only.
- Items with no attempts come first.
- Then order by `test_design_item.updated_at`.
- Then order by `test_design_item.id`.

After an item is attempted, `updated_at` is refreshed, moving it behind other unmastered items.

Assigning designs return `409` with code `design_not_learning_for_next_check`.

### POST /api/test-designs/{test_design_id}/learning-attempts

Submits one learning-check attempt.

Request:

```json
{
  "test_design_item_id": 1,
  "user_answer": "memory",
  "response_time_ms": 2500
}
```

`user_answer` is required and may be an empty string. `response_time_ms` may be null but cannot be negative.

The service scores the answer with the exact answer policy, inserts one `vocabulary_attempt` with `attempt_type = learning_check`, no assignment, no actual retention seconds, and `is_valid_for_fitting = false`, then updates the design item counters in the same transaction.

Mastery requires two consecutive correct answers for the same item. An incorrect answer resets only `consecutive_correct_count`; total `correct_count` is preserved.

When all fixed-pool items are mastered, the same transaction transitions the design from `learning` to `assigning`. Assignment rows are not created in Stage 4.

Response:

```json
{
  "attempt_id": 1,
  "test_design_item_id": 1,
  "is_correct": true,
  "canonical_answer": "memory",
  "attempt_count": 2,
  "correct_count": 2,
  "consecutive_correct_count": 2,
  "is_mastered": true,
  "mastered_at": "UTC timestamp or null",
  "mastered_item_count": 15,
  "required_item_count": 100,
  "remaining_item_count": 85,
  "design_status": "learning"
}
```

The canonical answer is returned only after submission as corrective feedback.

### GET /api/test-designs/{test_design_id}/learning-progress

Returns aggregate learning progress calculated from persisted rows:

```json
{
  "test_design_id": 1,
  "status": "learning",
  "required_item_count": 100,
  "pool_item_count": 100,
  "mastered_item_count": 15,
  "remaining_item_count": 85,
  "total_attempt_count": 73,
  "correct_attempt_count": 48,
  "learning_started_at": "UTC timestamp"
}
```

This endpoint is available for `learning` and `assigning` designs so the final learning state remains readable after automatic transition.

### POST /api/test-designs/{test_design_id}/initialize-assignments

Initializes deterministic retention-group assignments for an `assigning` design and transitions it to `activation_review`.

The service validates that the fixed learning pool contains exactly `required_item_count` mastered items, that the design has exactly `group_count` pending groups with unique positive intervals, and that no assignments already exist.

Assignment uses the stored `random_seed` with the separate namespace `group_assignment`:

```text
SHA256(f"{random_seed}:group_assignment")
```

The service sorts `test_design_item.id` values, shuffles them with a local `random.Random`, loads groups by `group_index`, and assigns shuffled items round-robin across groups. This gives every group exactly `items_per_group` assignments and interleaves retention intervals during activation review.

Persisted `test_assignments` become the source of truth. The service never recomputes or reshuffles them after initialization.

Response:

```json
{
  "test_design_id": 1,
  "status": "activation_review",
  "assignment_count": 100,
  "group_count": 5,
  "items_per_group": 20,
  "random_seed": 12345,
  "groups": [
    {
      "test_design_group_id": 1,
      "group_index": 1,
      "interval_seconds": 600,
      "assignment_count": 20
    }
  ],
  "activation_review_started_at": "UTC timestamp"
}
```

This endpoint does not expose English answers and does not create vocabulary attempts.

### GET /api/test-designs/{test_design_id}/activation-review/next

Returns the awaiting-anchor assignment with the lowest global `assignment_order`.

Activation review is not a test. It is an explicit review step, so the response includes both `korean` and `english_answer`. No `vocabulary_attempt` rows are created.

### POST /api/test-designs/{test_design_id}/activation-review/{assignment_id}/complete

Completes one activation-review item in global assignment order. The server generates `anchor_at`, calculates `scheduled_at = anchor_at + interval_seconds`, changes the assignment from `awaiting_anchor` to `pending`, and leaves `completed_at` null.

Participants cannot skip ahead. Repeated completion for the same assignment returns a conflict and never overwrites `anchor_at` or `scheduled_at`.

When the final assignment is anchored, the design transitions from `activation_review` to `active` and stores `activated_at`. Assignment completion and the final design transition happen in one transaction.

This endpoint does not score answers and does not create delayed-recall rows.

### GET /api/test-designs/{test_design_id}/activation-review/progress

Returns activation progress calculated from persisted assignments. It is readable in both `activation_review` and `active` status.

### GET /api/test-designs/{test_design_id}/assignment-schedule

Returns read-only group schedule summaries in `group_index` order. It includes assignment counts, awaiting-anchor counts, pending counts, completed counts, and earliest/latest scheduled timestamps. It does not expose English answers and does not calculate group accuracy.

No persistent due status is stored. A pending assignment is due only when `status = pending` and `scheduled_at <= current UTC time`. Due retrieval and delayed answer submission remain Stage 6.

Stage 6 delayed tests should use the actual elapsed time from each assignment's `anchor_at` and delayed response timestamp, not only the target `interval_seconds`.

### GET /api/test-designs/{test_design_id}/delayed-recalls/next

Returns the earliest due delayed-recall assignment for an `active` design.

Due state is derived, never persisted:

```text
assignment.status = pending
and assignment.scheduled_at <= current UTC time
```

Due assignments are ordered by `scheduled_at`, then `assignment_order`, then assignment ID. The response does not expose `english_answer`, normalized canonical answers, correctness, or `anchor_at`.

If no pending assignment is currently due, the endpoint returns `available = false` with `next_scheduled_at` when a future pending assignment exists. It does not return 404 merely because nothing is due.

### POST /api/test-designs/{test_design_id}/delayed-recalls/{assignment_id}

Submits one due delayed-recall answer for an active design.

Request:

```json
{
  "user_answer": "memory",
  "response_time_ms": 3200
}
```

The server rejects early submissions, accepts late submissions, captures `attempted_at`, calculates `actual_retention_seconds = attempted_at - anchor_at` in whole seconds, scores with the exact answer policy, inserts one `delayed_recall` vocabulary attempt, and marks the assignment `completed`.

During active delayed testing, no corrective feedback is returned. The response does not include the canonical answer, normalized canonical answer, or `is_correct`.

`lateness_seconds` is calculated only for the response as `max(0, attempted_at - scheduled_at)`. It is not stored.

After each submission, the service checks whether the assignment's group is complete. A group completes only when all assignments in that group are completed and each has exactly one valid delayed-recall attempt. After that, the service checks whether the whole design is complete. Delayed-recall submission does not create `curve_models` rows or fit a curve automatically.

### GET /api/test-designs/{test_design_id}/delayed-recalls/progress

Returns delayed-recall progress for `active` and `completed` designs. All counters are calculated from persisted assignments and groups.

### GET /api/test-designs/{test_design_id}/retention-summary

Returns raw observed retention summaries by group for `active` and `completed` designs. Group summaries include calculated correct/incorrect counts, observed accuracy, and actual-retention statistics from valid delayed-recall rows.

Partial groups may show partial raw observations, but only completed groups count as complete time points. Stage 7 official curves are created and read through separate curve-model endpoints; this raw summary response does not expose raw user answers or canonical English answers.

### GET /api/participants/{participant_id}/retention-history

Returns raw retention summaries for the participant's active and completed designs ordered by design creation time. The endpoint does not fit a curve, create curve models, combine percentages into a model, or expose raw/canonical answers.

### GET /api/participants/{participant_id}/test-designs/current

Returns the participant's current non-terminal design. Non-terminal statuses are `draft`, `learning`, `assigning`, `activation_review`, and `active`.

If the participant exists but has no current design, the API returns `404` with code `current_test_design_not_found`. This keeps the absence explicit for the local MVP client.

## Curve Models

Stage 7 curve endpoints create and read official personal forgetting-curve versions. They use item-level delayed-recall observations only; raw group percentages are returned as observed points but are not fitted.

### GET /api/test-designs/{test_design_id}/curve-eligibility

Returns a read-only eligibility report for fitting an official curve using completed historical data through the trigger design.

Response:

```json
{
  "test_design_id": 1,
  "participant_id": 1,
  "design_status": "completed",
  "eligible": true,
  "complete_time_point_count": 5,
  "sample_count": 100,
  "correct_count": 64,
  "incorrect_count": 36,
  "has_existing_curve": false,
  "next_version": 1,
  "reasons": []
}
```

Eligibility failures include `design_not_completed`, `out_of_order_trigger`, `fewer_than_five_complete_time_points`, `no_valid_delayed_results`, `all_results_correct`, `all_results_incorrect`, and `insufficient_distinct_times`.

### POST /api/test-designs/{test_design_id}/curve-model

Fits and stores one official append-only curve model for a completed trigger design. The endpoint is idempotent for the same trigger design: if a row already exists, it returns the stored model with `created = false`.

Response:

```json
{
  "created": true,
  "curve": {
    "id": 1,
    "participant_id": 1,
    "trigger_test_design_id": 1,
    "version": 1,
    "display_name": "Personal Curve V1",
    "model_name": "exponential_power",
    "fit_method": "bernoulli_mle",
    "T_seconds": 12345.6,
    "c": 0.82,
    "log_likelihood": -42.5,
    "sample_count": 100,
    "complete_time_point_count": 5,
    "converged": true,
    "data_cutoff_at": "UTC timestamp",
    "fitted_at": "UTC timestamp"
  },
  "observed_points": [
    {
      "test_design_id": 1,
      "test_design_group_id": 1,
      "group_index": 1,
      "target_interval_seconds": 600,
      "mean_actual_retention_seconds": 617.4,
      "minimum_actual_retention_seconds": 601,
      "maximum_actual_retention_seconds": 641,
      "correct_count": 18,
      "total_count": 20,
      "observed_accuracy": 0.9
    }
  ],
  "predicted_points": [
    {
      "time_seconds": 601.0,
      "predicted_retention": 0.93
    }
  ],
  "warnings": []
}
```

The model is `R(t) = exp(-((t / T) ** c))` with `b` fixed at `1`. `T_seconds` is stored in seconds, `c` is positive, and `log_likelihood` is the maximized Bernoulli log likelihood, not a negative loss.

Conflict responses include `design_not_completed`, `out_of_order_trigger`, and duplicate insert conflicts. Fitting or eligibility failures return a validation error without inserting a row and without invented `T` or `c` values.

### GET /api/participants/{participant_id}/curve-models

Lists official curve metadata for a participant ordered by version. Missing participants return `404` with code `participant_not_found`.

### GET /api/participants/{participant_id}/curve-models/latest

Returns the latest official curve, observed points reconstructed from the source cutoff, and 100 smooth predicted points. Participants without a model return `404` with code `curve_model_not_found`.

### GET /api/participants/{participant_id}/curve-models/{version}

Returns one historical curve version and its reconstructed observed and predicted points. Missing versions return `404` with code `curve_version_not_found`.

## Not Yet Implemented

Stage 7 does not implement participant-facing frontend pages, frontend curve charts, provisional curves, alternative models, confidence intervals, bootstrap analysis, model comparison, notifications, background jobs, authentication, admin pages, or CSV export.
