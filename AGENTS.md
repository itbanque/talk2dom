# Repository Guidelines

## Project Structure & Module Organization
- `talk2dom/` is the main Python package. API routes live under `talk2dom/api/`, database models and sessions under `talk2dom/db/`, and prompt/templates assets under `talk2dom/prompts/` and `talk2dom/templates/`.
- `tests/` contains pytest suites, organized by feature area (e.g., `tests/api/`, `tests/db/`).
- `alembic/` and `alembic.ini` hold database migrations.
- Deployment artifacts include `Dockerfile`, `docker-compose.yml`, and Helm charts under `charts/`.
- Helper scripts like `start_api.sh` and `deploy_k8s.sh` live at repo root.

## Build, Test, and Development Commands
- `docker compose up` starts the full local stack (API, Postgres, Redis).
- `./start_api.sh` loads `.env` and runs the FastAPI server with reload.
- `poetry install` installs dependencies defined in `pyproject.toml`.
- `poetry shell` enters the Poetry-managed virtualenv.
- `poetry run pytest` runs the test suite.
- `poetry run black .` formats Python code; `poetry run ruff check .` runs linting.

## Coding Style & Naming Conventions
- Python 3.12 target; use 4-space indentation and `snake_case` for modules/functions.
- Format with Black and keep code lint-clean under Ruff.
- Tests follow `test_*.py` filenames and `test_*` function names.

## Testing Guidelines
- Framework: pytest (see `tests/`).
- Add or update tests for new behavior, especially API routes and DB logic.
- Any new function or library must include a unit test.
- Run targeted tests when possible (e.g., `poetry run pytest tests/api`).

## Commit & Pull Request Guidelines
- Commit history shows short, plain summaries (e.g., “fix bug”, “add redis”); keep messages concise and imperative.
- Base branch is `main`; keep PRs small and focused.
- PRs should note what changed and how to test, and include formatting/linting compliance as per `CONTRIBUTING.md`.

## Configuration & Secrets
- Environment files (`.env`, `.env.local`, `.env.staging`, `.env.prod`) drive runtime config.
- Never commit real secrets; use placeholders for examples.
