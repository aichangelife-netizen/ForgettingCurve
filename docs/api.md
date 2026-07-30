# API

All Stage 3 API paths are mounted under `/api`. Responses use JSON. Service-layer errors use:

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

Transitions a design from `draft` to `learning` and stores `learning_started_at` in one transaction.

Repeated requests or calls for non-draft designs return `409` with code `invalid_design_status_transition`. The timestamp is not silently overwritten.

This endpoint does not implement the learning flow.

### GET /api/participants/{participant_id}/test-designs/current

Returns the participant's current non-terminal design. Non-terminal statuses are `draft`, `learning`, `assigning`, `activation_review`, and `active`.

If the participant exists but has no current design, the API returns `404` with code `current_test_design_not_found`. This keeps the absence explicit for the local MVP client.

## Not Yet Implemented

Stage 3 does not implement learning attempts, mastery counter updates, random vocabulary grouping, assignment creation, activation review, anchor handling, delayed recall submission, curve fitting, curve model creation, authentication, admin pages, or participant-facing frontend pages.
