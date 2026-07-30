# Frontend Workflow

Stage 8 adds the participant-facing local MVP frontend. It uses the Next.js App Router, React client components for experiment state, a typed API client under `frontend/lib/api`, and local browser storage only for MVP resume behavior.

## Configuration

Set the API base URL with:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

The tracked `frontend/.env.example` contains this value. Do not create or commit a real `.env` or `.env.local` file. When the variable is absent, the frontend falls back to `http://127.0.0.1:8000`.

The backend allows CORS only from local frontend origins:

- `http://localhost:3000`
- `http://127.0.0.1:3000`

## Routes

- `/`: landing page with Create New Participant and Resume Current Experiment.
- `/experiment`: participant dashboard with current status, next action, and latest official curve summary.
- `/experiment/design`: design creation with editable intervals and Development/Research presets.
- `/experiment/[testDesignId]/learn`: study materials and learning-check modes.
- `/experiment/[testDesignId]/activation`: final review and per-word memory-time anchoring.
- `/experiment/[testDesignId]/delayed`: due delayed-recall testing and waiting state.
- `/experiment/[testDesignId]/results`: raw summaries, curve generation, chart, and historical curve selection.

## Participant Session

Creating a participant calls `POST /api/participants` and stores only `participantId` and `participantCode` in `localStorage`. It does not store names, email addresses, passwords, typed answers, or authentication secrets.

The local session is not authentication. It is only local MVP persistence so a participant can resume on the same browser. Corrupted session data is cleared. If the backend no longer has the participant, the frontend clears the local session and asks the participant to start again.

## Experiment Flow

The design page validates user input before sending raw integer seconds to the backend. It displays `group_count`, `required_item_count`, readable interval labels, and the sentence `This experiment requires mastering X vocabulary items.` Backend validation remains authoritative.

Learning has two modes. Study mode shows Korean words with canonical English answers and does not create attempts. Learning-check mode shows only the Korean prompt before submission, measures client response time, and sends the answer through the learning-attempt endpoint. Feedback appears only after submission.

Assignment initialization is an explicit user action. The frontend explains that mastered words will be assigned evenly to retention intervals and then calls the backend initialization endpoint.

Activation review is not a test. It shows Korean and English together, and each explicit review action creates that word's memory-time anchor on the backend.

Delayed recall uses backend due state. When no item is due, the page shows the next scheduled time, a countdown, and a refresh button, with modest polling while the page is open. When an item is due, it shows only the Korean word. After submission, it shows only `Response recorded.` It never displays correctness or the canonical answer during an active experiment.

## Results And Curves

The results page displays raw retention summaries first. Partial and complete time points are labeled separately. If fewer than five complete time points exist, it displays the insufficient-data message and does not render a provisional curve.

When a completed design is eligible and no curve exists for its trigger, the participant can explicitly generate an official curve. The frontend prevents duplicate clicks while the request is in flight. Existing curve versions are read-only.

The curve chart is a lightweight responsive SVG. Observed points are visible markers and are not connected to each other. The fitted line uses backend `predicted_points`; the frontend does not calculate or refit a curve. X positions use logarithmic placement for positive actual retention times, and y positions are linear probabilities clamped to `0..1`. A text table below the chart provides the same observed-point details.

Known limitations:

- Browser localStorage is not cross-device persistence or authentication.
- Countdown text is only a convenience; the backend decides whether a test is due.
- The frontend does not include notifications or background tasks.
- No admin, authentication, CSV export, confidence interval, or provisional curve UI is implemented.
