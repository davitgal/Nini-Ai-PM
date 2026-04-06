# Nini AI Agent — Project Status

## Overview

**Nini** — персональный AI проект-менеджер для Давита. Агрегирует задачи из нескольких ClickUp воркспейсов в единую систему с приоритизацией (Money > Stakeholders > Deadlines). Telegram-бот с интеллектом Claude для управления задачами через естественный язык.

**Архитектура:** Monorepo (`backend/` + `frontend/`), single-user сейчас, multi-tenant ready.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, SQLAlchemy async, asyncpg |
| Database | Supabase Cloud (PostgreSQL 17.6, Seoul region) |
| Migrations | Alembic |
| ClickUp API | httpx async, rate limiter (100 req/min) |
| AI (Phase 2) | Anthropic Claude API |
| Bot (Phase 2) | python-telegram-bot / aiogram |
| Frontend (Phase 4) | React (Telegram Mini App) |
| Package Manager | uv |
| Deploy | Railway (backend), Vercel (frontend) |

---

## Database Schema (6 tables)

| Table | Records | Description |
|-------|---------|-------------|
| `users` | 1 | Davit's profile |
| `workspaces` | 1 | TrueCodeLab (team_id: 9014579452) |
| `projects` | — | Spaces/Folders/Lists (repopulated after reset) |
| `unified_tasks` | ~11 | Only "Доска задач" list (list_id: 901410057231) |
| `sync_log` | — | Webhook event audit trail |
| `knowledge_base` | — | RAG storage (Phase 2) |

---

## ClickUp Workspaces

| Workspace | Status | Team ID | Token |
|-----------|--------|---------|-------|
| TrueCodeLab | Synced (1 list: "Доска задач") | 9014579452 | Configured |
| Yerevan Mall | Not connected | — | Needs token |
| CubicSoft | Not connected | — | Needs token |

---

## API Endpoints (14 total)

### Health
- `GET /health` — Service status
- `GET /health/db` — Database connectivity

### Tasks
- `GET /api/v1/tasks` — List tasks (filters: company, status, priority, assignee, overdue)
- `GET /api/v1/tasks/stats` — Aggregated statistics
- `GET /api/v1/tasks/{id}` — Single task
- `PATCH /api/v1/tasks/{id}` — Update task locally
- `POST /api/v1/tasks/{id}/sync-to-clickup` — Push changes to ClickUp

### Projects
- `GET /api/v1/projects` — List all projects
- `GET /api/v1/projects/{id}` — Single project

### Sync
- `POST /api/v1/sync/full` — Trigger full sync
- `GET /api/v1/sync/status` — Sync status
- `GET /api/v1/sync/log` — Sync event log
- `POST /api/v1/sync/register-webhook` — Register ClickUp webhook
- `POST /api/v1/sync/webhook` — Webhook receiver (legacy route)

### Webhooks
- `POST /api/v1/webhooks/clickup` — ClickUp webhook endpoint

---

## Key Architectural Decisions

1. **Fetch full task on every webhook** — один код-пасс нормализации, минимальная нагрузка на API при текущем объёме
2. **sync_hash (MD5)** — предотвращает лишние записи и бесконечные циклы двусторонней синхронизации
3. **Dual company resolution** — сначала кастом-поле "Company", потом имя папки как fallback
4. **Dual DB connections** — PgBouncer (port 6543) для API, Direct (port 5432) для sync/migrations
5. **user_id everywhere** — готовность к multi-tenancy
6. **Commit per list** — sync коммитит после каждого списка, чтобы избежать statement_timeout
7. **Skip closed tasks on insert** — задачи с `status_type=closed` не создаются в БД, но обновляются если уже есть
8. **Single-list sync mode** — временно синкается только список `901410057231` ("Доска задач") через `DEV_SYNC_LIST_ID` в scheduler и frontend

---

## Company Distribution (TrueCodeLab)

| Company | Tasks | Company | Tasks |
|---------|-------|---------|-------|
| Санек | 563 | Chomp&Chomp | 46 |
| Updevision | 81 | Cubics Soft | 27 |
| Yerevan Mall | 75 | Garage Mall | 26 |
| GMM | 55 | YM Admin Panel | 26 |
| (untagged) | 55 | Own | 17 |
| Alocator EXT | 47 | TrueCodeLab | 12 |

**Overdue tasks:** 28

---

## File Structure

```
nini-ai-agent/
├── backend/
│   ├── alembic/                    # DB migrations
│   ├── app/
│   │   ├── main.py                 # FastAPI app + lifespan
│   │   ├── config.py               # pydantic-settings
│   │   ├── database.py             # Dual engines (pooled + direct)
│   │   ├── dependencies.py         # DI (get_db, get_user)
│   │   ├── models/                 # SQLAlchemy ORM (6 tables)
│   │   ├── schemas/                # Pydantic request/response
│   │   ├── routers/                # health, tasks, projects, sync, webhooks
│   │   ├── services/
│   │   │   ├── clickup/            # client, normalizer, webhook_handler, task_sync
│   │   │   └── sync_engine.py      # Full sync orchestrator
│   │   ├── core/                   # exceptions, logging
│   │   └── tasks/                  # Background sync scheduler (6h)
│   ├── tests/                      # 7 tests (normalizer)
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env
├── frontend/                       # Phase 4 — React stub
├── docker-compose.dev.yml
├── Makefile
├── PROJECT_STATUS.md               # This file
└── TODO.md                         # Task tracker
```
