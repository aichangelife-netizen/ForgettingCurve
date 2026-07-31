# Experiment Protocol

This document describes the local MVP protocol implemented by the backend and participant-facing frontend. Demonstration vocabulary is included for development and review only; formal research use should replace it with approved research material.

## Selection And Design

Participants are anonymous local records. The system creates a generated `participant_code` and does not request names, email addresses, passwords, or other identifying fields.

A test design belongs to one participant and defines:

- `items_per_group`
- a list of positive, unique retention intervals in seconds
- `group_count = len(intervals_seconds)`
- `required_item_count = items_per_group * group_count`
- one stored random seed

At most one unfinished design may exist per participant. Unfinished statuses are `draft`, `learning`, `assigning`, `activation_review`, and `active`.

## Exact-Answer Policy

The MVP uses exact English-answer matching after normalization. Normalization is documented in `docs/vocabulary-policy.md`. The response stored in `vocabulary_attempts.user_answer` is the raw submitted answer, while `normalized_answer` stores the normalized submitted answer used for checking.

## Learning And Mastery

Starting learning freezes a fixed learning pool by selecting exactly `required_item_count` active vocabulary items. The learning pool is persisted as `test_design_items`; later vocabulary activation changes do not alter it.

Learning checks show the Korean prompt only before submission. After submission, the backend returns correctness and the canonical answer as feedback.

Mastery requires two consecutive correct answers for the same item. Incorrect learning answers reset only `consecutive_correct_count`; they do not reset `attempt_count` or `correct_count`.

When every item in the fixed learning pool is mastered, the design transitions from `learning` to `assigning`.

## Deterministic Assignment

Assignment initialization is an explicit action from `assigning` status. The service sorts design item IDs, shuffles them with the stored random seed under the `group_assignment` namespace, and assigns items round-robin to groups ordered by `group_index`.

Every mastered design item receives exactly one assignment. Every group receives exactly `items_per_group` assignments. Assignment order is deterministic and covers `1..required_item_count`.

## Activation Review

Activation review is a final review, not a test. It shows both Korean and English. Participants cannot skip ahead; assignments must be reviewed in assignment order.

Each activation-review completion stores that assignment's own `anchor_at` timestamp and calculates:

```text
scheduled_at = anchor_at + interval_seconds
```

When every assignment is anchored, the design transitions from `activation_review` to `active`.

## Delayed Recall

Due state is derived at request time:

```text
assignment.status = pending
and assignment.scheduled_at <= current UTC time
```

Only due pending assignments are returned. Early delayed submission is rejected. Late delayed submission is accepted.

During active delayed testing, the prompt shows only the Korean word. The API response does not expose correctness or the canonical answer. The participant-facing frontend displays only a neutral confirmation after submission.

The backend records:

```text
attempted_at = server UTC time
actual_retention_seconds = attempted_at - anchor_at
```

The client does not provide research timestamps.

Stored timestamps and API transport timestamps are UTC. API responses include a timezone suffix such as `Z`; the participant-facing browser converts those instants to local display time and includes a timezone abbreviation or offset. Display formatting never changes `actual_retention_seconds`.

Each assignment can have at most one delayed-recall attempt.

## Completion

A group becomes a complete time point only when all assignments in the group are completed and every assignment has exactly one valid delayed-recall result.

A design becomes completed only when every group is completed and every assignment has exactly one valid delayed-recall result.

Partial groups may appear in raw summaries but are not complete time points.

## Official Personal Curves

Official curves require at least five complete time points. A complete time point is one completed `test_design_group`, not merely one unique target interval value.

Official fitting uses only valid delayed-recall item-level rows from completed designs through the trigger design. It uses `actual_retention_seconds`, not target intervals or group percentages. No fabricated `t = 0` observation is added.

The fitted model is:

```text
R(t) = exp(-((t / T) ** c))
```

`b` is fixed at `1`. `T` and `c` are fitted by item-level Bernoulli maximum likelihood.

Curve rows are append-only:

- first official curve: `Personal Curve V1`
- later completed trigger design: `Personal Curve V2`
- later completed trigger design: `Personal Curve V3`

Old versions are historical snapshots. Creating a later version does not update or refit older versions. Historical versions exclude data from later completed designs.

## Known Limitations

- Demonstration vocabulary is not formal research material.
- SQLite is suitable for the local MVP but not ideal for concurrent multi-user deployment.
- SQLite does not preserve timezone metadata; application code treats stored timestamps as UTC.
- No authentication is implemented.
- Browser localStorage is local resume persistence only.
- The fitted curve has no confidence intervals, bootstrap analysis, model comparison, or alternative models.
