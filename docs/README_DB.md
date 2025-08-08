# Database Setup and Migrations

## Prerequisites

- PostgreSQL running locally and database `mcp_server` created
- Set `DATABASE_URL` in `.env` or environment

## Install Dependencies

- Ensure pip is available in venv, or install globally: `python -m ensurepip --upgrade`
- `pip install -e .`

## Initialize Alembic (already added)

- `alembic init` already configured in repo

## Generate Initial Migration

- `alembic revision --autogenerate -m "create oauth_tokens table"`

## Apply Migration

- `alembic upgrade head`

