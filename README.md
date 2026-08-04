# PetroMatch

PetroMatch is a low-maintenance job-alert ingestion pipeline:

- FastAPI backend
- Next.js dashboard
- PostgreSQL via SQLAlchemy and Alembic
- Gmail API ingestion
- deterministic LinkedIn email extraction
- local Docker Compose development
- production deployment on Vercel plus Supabase

The current production goal is to keep Gmail ingestion, LinkedIn parsing, deduplication, job storage, and the dashboard reliable before adding scrapers or additional job sources.

## A. Local Development

Start the full local stack:

```bash
cd backend
docker compose up --build
```

The services are:

- API: `http://localhost:8000`
- Dashboard: `http://localhost:3000`
- PostgreSQL: `localhost:5432`

Run migrations locally:

```bash
cd backend
cp .env.example .env
alembic upgrade head
```

Run the API without Docker:

```bash
cd backend
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

Run the frontend without Docker:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Run tests:

```bash
cd backend
pytest
```

Build the frontend:

```bash
cd frontend
npm run build
```

## B. GitHub

Use a private GitHub repository.

Before pushing, confirm no secrets are tracked:

```bash
git status --short
git ls-files | grep -E '(\.env|token|secret|\.secrets)' || true
```

The repository should not contain Gmail tokens, Google client secrets, database passwords, Supabase service credentials, `CRON_SECRET`, or production `.env` files.

Push the project:

```bash
git remote add origin git@github.com:<owner>/<private-repo>.git
git push -u origin main
```

## C. Supabase

Create a Supabase project and use the hosted PostgreSQL database.

For Vercel serverless functions, use Supabase’s pooled PostgreSQL connection string. In Supabase, find the connection pooler string, usually under database connection settings. Prefer the pooler URL suitable for serverless usage and include SSL if Supabase provides it.

For SQLAlchemy with psycopg, use this shape:

```text
postgresql+psycopg://<user>:<password>@<pooler-host>:<pooler-port>/<database>?sslmode=require
```

Run production migrations manually from your machine:

```bash
cd backend
DATABASE_URL='postgresql+psycopg://<user>:<password>@<pooler-host>:<pooler-port>/<database>?sslmode=require' \
  alembic upgrade head
```

Do not run migrations automatically on Vercel requests.

Verify tables:

```bash
psql '<supabase-pooled-connection-string>' -c '\dt'
```

### One-Off Historical Data Copy

After Alembic has created the Supabase schema, copy historical local PostgreSQL data with the one-off copy script. The script uses separate source and target variables and does not read the application `DATABASE_URL`.

```bash
cd backend
export LOCAL_DATABASE_URL='postgresql+psycopg://<local-user>:<local-password>@localhost:5432/petromatch'
export SUPABASE_DATABASE_URL='postgresql+psycopg://<supabase-user>:<supabase-password>@<pooler-host>:<pooler-port>/<database>?sslmode=require'
```

Preview the copy without writes:

```bash
python -m app.scripts.copy_local_to_supabase --dry-run
```

Apply the copy:

```bash
python -m app.scripts.copy_local_to_supabase --apply
```

The script copies active application tables in foreign-key order:

- `ingestion_runs`
- `processed_emails`
- `jobs`

It does not copy `alembic_version`. Primary keys, foreign keys, Gmail message IDs, job URLs, external IDs, deduplication fields, metadata, and timestamp values are preserved. Existing target rows are skipped using stable unique identifiers: primary keys, Gmail message IDs, job URLs, `(source, external_id)`, and dedupe fingerprints where available.

After preserved numeric IDs are inserted, PostgreSQL sequences in Supabase are reset above the highest existing ID so future inserts continue safely. The script prints database host/database labels only and does not print passwords or full connection strings.

## D. Vercel

Use two Vercel projects from the same private GitHub repository.

Frontend project:

- Root directory: `frontend`
- Framework preset: Next.js
- Environment variable:
  - `NEXT_PUBLIC_API_URL=https://<api-domain>`

Backend project:

- Root directory: `backend`
- Runtime: Vercel Python Function
- Entry point: `backend/api/index.py`
- Routing and cron config: `backend/vercel.json`
- Environment variables:
  - `DATABASE_URL`
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GMAIL_TOKEN_JSON`
  - `CRON_SECRET`
  - `ALLOWED_ORIGINS=https://<frontend-domain>`
  - `GMAIL_QUERY=is:unread`
  - `GMAIL_MAX_RESULTS=50`

Configure preview and production environments separately. For production, set `NEXT_PUBLIC_API_URL` to the deployed backend URL and `ALLOWED_ORIGINS` to the deployed frontend URL. For preview deployments, add the relevant preview frontend origin if you intend to test previews against the backend.

## E. Gmail Credentials

Local development can continue to use:

```text
backend/.secrets/google_oauth_client.json
backend/.secrets/gmail_token.json
```

For production, set:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GMAIL_TOKEN_JSON`

To convert an existing local token file into a Vercel environment value:

```bash
cd backend
python - <<'PY'
from pathlib import Path
print(Path('.secrets/gmail_token.json').read_text())
PY
```

Paste the full JSON output into `GMAIL_TOKEN_JSON`. Do not commit it.

The backend recreates Google credentials from `GMAIL_TOKEN_JSON` at runtime and refreshes expired access tokens using the refresh token. In production, refreshed credentials are kept in memory for that invocation and are not written back to the repository.

If Google revokes or expires the refresh token, run the local OAuth flow again with the dedicated Gmail account, then replace `GMAIL_TOKEN_JSON` in Vercel with the new token JSON.

## F. Vercel Cron

Cron path:

```text
GET /api/v1/cron/daily-ingestion
```

Schedule:

```text
0 23 * * *
```

This is 23:00 UTC, approximately 06:00 Thailand time the following morning. On the Vercel Hobby plan, daily cron jobs may run at some point within the scheduled hour rather than exactly at minute zero.

Vercel sends:

```text
Authorization: Bearer <CRON_SECRET>
```

Set `CRON_SECRET` in the backend Vercel project. Check Vercel logs after the scheduled execution.

## G. Manual Testing

Health check:

```bash
curl https://<api-domain>/health
```

Authorized cron test:

```bash
curl \
  -H "Authorization: Bearer <CRON_SECRET>" \
  https://<api-domain>/api/v1/cron/daily-ingestion
```

Unauthorized cron test:

```bash
curl -i https://<api-domain>/api/v1/cron/daily-ingestion
```

List jobs:

```bash
curl https://<api-domain>/api/v1/jobs
```

Local cron test:

```bash
curl \
  -H "Authorization: Bearer <CRON_SECRET>" \
  http://localhost:8000/api/v1/cron/daily-ingestion
```

## H. Rollback and Recovery

Vercel rollback:

- Open the relevant Vercel project.
- Go to Deployments.
- Select a previous healthy deployment.
- Use Promote/Rollback for that deployment.

Database migration rollback:

1. Confirm the migration is safe to reverse.
2. Back up the Supabase database if data could be affected.
3. Run:

```bash
cd backend
DATABASE_URL='<supabase-pooled-sqlalchemy-url>' alembic downgrade -1
```

Rerun ingestion safely:

```bash
curl \
  -H "Authorization: Bearer <CRON_SECRET>" \
  https://<api-domain>/api/v1/cron/daily-ingestion
```

The ingestion pipeline is idempotent: already processed Gmail message IDs are skipped, and duplicate jobs are skipped by URL, external ID, or conservative fingerprint.

Diagnose Gmail authentication failures:

- Confirm `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` match the OAuth client used to generate the token.
- Confirm `GMAIL_TOKEN_JSON` is valid JSON and includes a `refresh_token`.
- Check Vercel logs for safe error messages.
- If refresh fails, regenerate the local Gmail token and update `GMAIL_TOKEN_JSON`.

## Production Environment Variables

Backend:

```text
DATABASE_URL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GMAIL_TOKEN_JSON=
CRON_SECRET=
ALLOWED_ORIGINS=
GMAIL_QUERY=is:unread
GMAIL_MAX_RESULTS=50
DB_POOL_SIZE=1
DB_MAX_OVERFLOW=2
DB_POOL_RECYCLE_SECONDS=300
```

Frontend:

```text
NEXT_PUBLIC_API_URL=
```
