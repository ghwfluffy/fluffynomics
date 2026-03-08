# Fluffynomics - Wealth Tracker

![Fluffynomics Banner](web/vue/public/banner.png)

Fluffynomics brings your accounts and investments together so you can track your wealth and plan ahead.

## Why Fluffynomics?

- Unified account tracking across checking, savings, credit, loan, retirement, stocks, and crypto.
- Secure user isolation: each user only sees their own objects.
- Practical planning model: balances, rates, fees, billing cycles, payment dates, and notes.
- Docker-first local development with a Vue frontend + FastAPI backend + Postgres.

## Core Features

- Account CRUD across multiple account types with type-specific fields.
- Stock catalog + stock positions for stock account tracking.
- Crypto positions and cash denominations.
- Cookie-based encrypted/signed sessions.
- Optional bearer-token auth using the same session token returned by login.
- Database schema upgrades via incremental SQL migrations (no volume wipe required).

## Tech Stack

- Frontend: Vue 3, TypeScript, Vuetify, Vite
- Backend: FastAPI, SQLAlchemy, Pydantic
- Database: PostgreSQL 16
- Infra: Docker Compose

## Architecture (High Level)

- `web/`: Vue app + NGINX container for TLS/static serving
- `python/`: FastAPI app, ORM models, API routes, DB upgrade logic
- `python/mp/db/migrations/`: schema source of truth and revisioned upgrades
- `docker-compose.yml`: local service orchestration
