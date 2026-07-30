# Curve Fitting

Stage 7 implements the official backend fitting path for personal forgetting curves. It does not implement frontend charts, provisional curves, alternative models, confidence intervals, bootstrap analysis, model comparison, notifications, background jobs, authentication, admin pages, or CSV export.

## Model

The fitted model is exactly:

```text
R(t) = exp(-((t / T) ** c))
```

- `b` is fixed at `1`; it is not estimated or stored.
- `T` is positive and stored in seconds as `curve_models.T`.
- `c` is positive and stored as `curve_models.c`.
- `t` is `vocabulary_attempts.actual_retention_seconds`.
- No synthetic `t = 0` point is added.

The implementation uses delayed-recall item-level binary correctness. It does not fit group percentages, target intervals, learning checks, or activation-review events.

## Source Data

An observation is eligible only when all of these are true:

- `vocabulary_attempts.attempt_type = delayed_recall`
- `vocabulary_attempts.is_valid_for_fitting = true`
- `vocabulary_attempts.actual_retention_seconds` is not null and greater than `0`
- the linked assignment is `completed`
- the linked test-design group is `completed`
- the linked test design is `completed`
- the design belongs to the fitted participant

For a trigger design, Stage 7 uses all eligible completed designs for that participant up to and including the trigger design. Completed designs are ordered by `completed_at`, then `id` as a deterministic tie-breaker. Data from later completed designs is excluded for older trigger versions.

## Eligibility

An official curve can be created only when:

- the trigger design exists and is completed
- at least 5 complete time points are available, where one complete time point is one completed `test_design_group`
- at least one correct delayed-recall result exists
- at least one incorrect delayed-recall result exists
- fitted retention times are positive
- at least two distinct actual retention times exist
- no later curve version has already been created out of chronological order

With 0 to 4 complete time points, raw retention summaries remain available through retention-summary endpoints, but no official curve is fitted or stored. All-correct and all-incorrect datasets are rejected as non-identifiable for this two-parameter fit.

## Likelihood

For each item:

```text
x_i = 1 when correct, otherwise 0
p_i = exp(-((t_i / T) ** c))
```

The service maximizes the Bernoulli log likelihood:

```text
sum_i [
  x_i * log(p_i)
  + (1 - x_i) * log(1 - p_i)
]
```

The stored `curve_models.log_likelihood` is this maximized log likelihood. It is not the negative log likelihood.

For numerical stability, the implementation evaluates:

```text
z = (t / T) ** c
log(p) = -z
log(1 - p) = log(-expm1(-z))
```

Invalid or non-finite observations raise fitting errors instead of being replaced with plausible values.

## Optimization

The fitting service uses NumPy `float64` arrays and SciPy `minimize` with L-BFGS-B on transformed parameters:

```text
log_T = log(T)
log_c = log(c)
```

Recovering `T = exp(log_T)` and `c = exp(log_c)` enforces positivity.

Parameter bounds are derived from the observed actual retention times:

```text
T_lower = max(min_actual_retention_seconds / 100, 1e-6)
T_upper = max(max_actual_retention_seconds * 100, T_lower * 10)
c_lower = 0.05
c_upper = 5.0
```

These bounds are numerical safeguards. They are not claims about human memory.

The optimizer uses deterministic starting points. `T` starts from the median time, geometric mean time, minimum time, and maximum time. `c` starts from `0.3`, `0.5`, `1.0`, and `2.0`. The converged solution with the highest log likelihood is selected.

Fit warnings can report that an optimum is near a bound, that the time range is limited, or that the sample count is low.

## Stored Versions

`curve_models` rows are append-only. The first official model for a participant is displayed as `Personal Curve V1`; later completed trigger designs create `Personal Curve V2`, `Personal Curve V3`, and so on.

The create endpoint is idempotent for the same trigger design. If a row already exists for the trigger, the stored version is returned with `created = false`.

Older versions are immutable: creating V2 does not update V1. Historical retrieval uses the stored trigger design as the cutoff and returns the observed points available through that trigger plus predicted points generated from the stored `T` and `c`.

Because SQLite does not provide strong row-level locks, Stage 7 relies on uniqueness constraints and transactional revalidation for practical duplicate protection in the local MVP. A production multi-user deployment should use a database such as PostgreSQL with stronger locking semantics.

## Returned Points

Observed points are summaries by completed test-design group. They include correct count, total count, observed accuracy, target interval, and actual-retention statistics. Duplicate target intervals from different completed designs remain separate observed points.

Predicted points are 100 smooth model points over the observed actual-retention range, using geometric spacing when the range has more than one value.
