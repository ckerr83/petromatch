# PetroMatch Backend MVP

This checkpoint resets the immediate MVP around forwarded job-alert emails.

Implemented in this phase:

- FastAPI application scaffold
- environment-based configuration
- SQLAlchemy session setup
- PostgreSQL schema models
- initial Alembic migration
- processed Gmail email traceability table
- normalized job opportunity table
- parser interface for source-specific email parsers
- read-only job API scaffold
- Gmail OAuth client setup
- one-pass unread Gmail email ingestion
- debug API for recent processed emails
- deterministic parser framework
- LinkedIn and generic email job extraction
- extraction status tracking on processed emails

Not implemented yet:

- dashboard
- scoring, scraping, authentication, scheduling, or application tracking

## Stack

- Python 3.11
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Gmail API client libraries

## Quick Start

1. Copy the sample environment file:

```bash
cp .env.example .env
```

2. Install dependencies locally:

```bash
pip install -e .
```

3. Run the database migration:

```bash
alembic upgrade head
```

4. Start the API:

```bash
uvicorn app.main:app --reload
```

5. Check the app is running:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## Current Endpoints

- `GET /api/v1/health`
- `GET /api/v1/emails`
- `POST /api/v1/emails/{email_id}/extract`
- `POST /api/v1/extraction/run`
- `POST /api/v1/ingestion/gmail/run`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`

## Gmail Credentials For The Next Phase

The default local paths are:

- OAuth client JSON: `.secrets/google_oauth_client.json`
- OAuth token cache: `.secrets/gmail_token.json`

`backend/.secrets/` is gitignored.

Place the Google OAuth client JSON at the configured path, then call:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingestion/gmail/run
```

On the first run, the Gmail client starts a local OAuth browser flow and writes the token cache to `.secrets/gmail_token.json`.
