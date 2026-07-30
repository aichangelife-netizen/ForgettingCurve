# Final MVP Audit

Stage 9 hardening status as of this repository state.

## Implemented Functionality

- Anonymous participant creation with generated participant codes.
- Draft test-design creation with positive unique intervals.
- Fixed learning-pool initialization.
- Exact-answer learning checks with two-consecutive-correct mastery.
- Automatic learning-to-assigning transition.
- Deterministic balanced group assignment.
- Ordered activation review with per-assignment anchors.
- Due delayed-recall retrieval and delayed answer submission.
- Group and design completion from valid delayed-recall data.
- Raw retention summaries and participant retention history.
- Official exponential-power curve fitting with append-only versions.
- Participant-facing frontend workflow through results and curve history.

## Automated Tests

- Backend pre-hardening preflight: `174 passed, 1 warning`.
- Stage 9 lifecycle integration test: added and passing.
- Final backend suite after Stage 9: `175 passed, 1 warning`.
- Frontend pre-hardening and Stage 9 checks: `12 passed`.

The warning is the existing Starlette/httpx `TestClient` deprecation warning.

## Bugs And Integrity Findings

- Fixed a SQLite learning-progress aggregate bug. `get_learning_progress` previously summed a boolean column for mastered item count; the service now counts mastered rows with an explicit SQL `CASE`.

## Manual Checks

- Clean-tree preflight completed before Stage 9 edits.
- Frontend route audit completed for landing, dashboard, design, learning, activation, delayed recall, and results.
- Repository scans are required in final verification for tracked environment files, databases, keys, tokens, credentials, private keys, and obvious secret patterns.

## Security Findings

- The app does not request names, emails, passwords, or authentication credentials.
- Browser persistence is limited to participant ID and participant code.
- Delayed recall does not expose canonical answers or correctness during active testing.
- CORS is restricted to documented local origins and does not enable wildcard origins with credentials.
- Backend service errors return stable JSON messages instead of stack traces.

## Dependency Findings

- `uv sync`: passed.
- `uv pip check`: passed.
- `npm install`: passed.
- `npm audit`: reports 12 high-severity findings, including dev-tooling transitive `brace-expansion` findings through eslint packages and production `next` transitive findings through `postcss` and `sharp`.
- `npm audit --omit=dev`: reports 3 high-severity production findings through `next` transitive `postcss` and `sharp`.
- `npm outdated`: reports newer `@types/react`, `@types/react-dom`, `eslint`, and `typescript`; it does not report a newer `next` in the current dependency range.

No low-risk compatible dependency change was applied. npm reports the available audit fix as `npm audit fix --force`, which would install breaking or regressive versions. The production audit findings should block public deployment until the upstream Next.js dependency chain has a compatible patched release or the project pins a safe reviewed version.

## SQLite Limitations

- SQLite does not preserve timezone metadata; application code treats loaded timestamps as UTC.
- SQLite does not provide strong row-level locks.
- The local MVP relies on constraints plus transactional revalidation for practical duplicate protection.
- PostgreSQL should be considered before concurrent multi-user use.

## Statistical Limitations

- The official model is fixed to `R(t) = exp(-((t / T) ** c))`.
- No confidence intervals, bootstrap analysis, model comparison, or alternative models are implemented.
- All-correct and all-incorrect datasets are rejected as non-identifiable for this two-parameter fit.
- Demonstration vocabulary is not formal research material.

## Unresolved Issues

- No code-level blocker is known for a controlled local pilot after final verification passes.
- Public deployment should remain blocked until HTTPS, authentication requirements, formal vocabulary, backup operations, privacy review, database concurrency needs, and npm production audit findings are addressed.

## Readiness Recommendation

The MVP is suitable for a local pilot experiment only after the final Stage 9 verification commands pass and the researcher accepts the documented SQLite and statistical limitations.
