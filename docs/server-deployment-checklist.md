# Server Deployment Checklist

This checklist is preparation guidance only. Stage 9 does not deploy the application.

## Runtime

- Use Python `3.12`, matching `backend/.python-version`.
- Use a current Node.js version compatible with Next.js 16.
- Install backend dependencies with `cd backend && uv sync`.
- Install frontend dependencies with `cd frontend && npm install`.

## Environment

- Set `FORGETTING_CURVE_DATABASE_URL` for the backend database location.
- Set `NEXT_PUBLIC_API_BASE_URL` for the frontend API URL.
- Keep `.env` and `.env.local` out of Git.
- Do not put secrets in `NEXT_PUBLIC_*` variables.

## Database

- Choose a database path outside source control.
- Run `cd backend && uv run alembic upgrade head` before starting the server.
- Back up the SQLite database before upgrades and before pilot sessions.
- Verify restore procedures before collecting pilot data.
- Keep filesystem permissions restricted to the application user.

SQLite is acceptable for a single-machine local MVP. Consider PostgreSQL before concurrent multi-user or public deployment because SQLite does not provide strong row-level locks.

## CORS And Network

- Restrict CORS origins to the exact frontend origins in use.
- Do not use wildcard CORS origins with credentials.
- Use HTTPS for any public or remote access.
- Put the backend behind a reverse proxy when exposing it beyond local development.
- Configure proxy timeouts and request-size limits conservatively.

## Process Management

- Run the backend with a process manager rather than an interactive shell.
- Build the frontend with `npm run build`.
- Serve the frontend with the hosting method selected for the environment.
- Capture logs without recording participant answers in application logs.

## Time And Files

- Configure the host for UTC or ensure system time is synchronized.
- The backend writes server-generated UTC timestamps.
- Protect the database file, backup directory, and any logs.
- Keep generated directories such as `.venv`, `node_modules`, `.next`, and cache folders out of source control.

## Recovery

- Document how to stop and restart backend and frontend processes.
- Document database backup location and restore commands.
- Test Alembic upgrade on a copy before applying it to pilot data.
- Keep a rollback plan for application code and database backups.
