# Tetrova Optical POS

Commercial optical retail software by **Tetrova Technologies**, initially configured for Weerasekara Optics.

## Architecture

- `apps/web` — one responsive React + TypeScript interface for desktop, tablet, phone, and the future Tauri shell
- `apps/api` — FastAPI modular monolith with tenant-aware authentication and persistence boundaries
- PostgreSQL — authoritative hosted database
- SQLite — supported by the same ORM for local development and the future desktop sync store
- Docker Compose — reproducible web, API, and PostgreSQL development stack

The default currency is LKR. Monetary values will be stored as integer minor units; floating-point values must never be used for billing.

## Quick start

### Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
```

Open the web app at <http://localhost:5173> and API docs at <http://localhost:8000/docs>. PostgreSQL is published on development port `55432` to avoid collisions with local installations.

### Local development

```bash
npm install
npm run dev

python3 -m venv .venv
./.venv/bin/pip install -r apps/api/requirements-dev.txt
cp .env.example .env
PYTHONPATH=apps/api ./.venv/bin/uvicorn app.main:app --reload
```

For SQLite, set `DATABASE_URL=sqlite:///./tetrova_pos.db`.

## Initial administrator

On an empty database the API creates the tenant and owner specified by `INITIAL_*` environment variables. Change the sample password before using any non-local environment. Bootstrap is disabled when `INITIAL_ADMIN_PASSWORD` is blank.

## Quality checks

```bash
npm run check
PYTHONPATH=apps/api ./.venv/bin/pytest apps/api/tests
PYTHONPATH=apps/api ./.venv/bin/ruff check apps/api
```

See [Phase 0 architecture](docs/architecture.md) and [security model](docs/security.md).

## Phase 1: customer management

Authenticated staff can register, search, view, and update customers, create and review visits, and receive duplicate-record warnings. Customer removal is a role-restricted soft archive. Every customer and visit query is tenant-scoped, and create/update/archive actions produce audit records.

## Phase 2: optical examinations

Customer profiles include tenant-scoped optical examination history, structured OD/OS measurements, incomplete draft saving, immutable finalization, superseding corrections, numerical comparison, and an A4 print/PDF view. Supported optical ranges and quarter-diopter enforcement are environment-configurable.

