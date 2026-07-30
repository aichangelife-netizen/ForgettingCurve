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

### GET /api/participants/{participant_id}/test-designs/current

Returns the participant's current non-terminal design. Non-terminal statuses are `draft`, `learning`, `assigning`, `activation_review`, and `active`.

If the participant exists but has no current design, the API returns `404` with code `current_test_design_not_found`. This keeps the absence explicit for the local MVP client.

## Not Yet Implemented

Stage 4 does not implement test group assignment, `test_assignment` creation, retention interval scheduling, activation review, anchor handling, delayed recall submission, curve fitting, curve model creation, authentication, admin pages, or participant-facing frontend pages.
