# Nini AI Agent — Project Status

## Overview

**Nini** — персональный AI проект-менеджер для Давита. Агрегирует задачи из нескольких ClickUp воркспейсов, приоритизирует по схеме Money > Stakeholders > Deadlines. Telegram-бот с интеллектом Claude — проактивный ассистент с ежедневными ритуалами (утренний план, перепланирование, итог дня) и краткосрочной памятью.

**Архитектура:** Monorepo (`backend/` + `frontend/`), single-user сейчас, multi-tenant ready.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13, FastAPI, SQLAlchemy async, asyncpg |
| Database | Supabase Cloud (PostgreSQL 17.6, Seoul region) |
| Migrations | Alembic |
| ClickUp API | httpx async, rate limiter (100 req/min) |
| AI | Anthropic Claude API (claude-sonnet-4-20250514) |
| Bot | aiogram 3, long polling |
| Frontend | React (Telegram Mini App), Vite, TailwindCSS |
| Package Manager | uv |
| Deploy | Railway (backend), Vercel (frontend) |

---

## Database Schema (10 tables)

| Table | Description |
|-------|-------------|
| `users` | Профиль Давита |
| `workspaces` | ClickUp команды (TrueCodeLab, etc.) |
| `projects` | Spaces / Folders / Lists иерархия |
| `unified_tasks` | Агрегированные задачи из ClickUp |
| `sync_log` | Аудит webhook-событий |
| `knowledge_base` | Persistent память Нини (RAG, Phase 3) |
| `daily_plans` | Утренние планы, перепланирования, итоги дня |
| `daily_states` | Статус ритуалов на каждый день (pending/done/skipped) |
| `daily_contexts` | Краткосрочная память: активность пользователя, история взаимодействий, риски |
| `nini_issues` | Backlog ошибок/проблем Нини (severity, status, source, resolution notes) |

---

## ClickUp Workspaces

| Workspace | Status | Team ID |
|-----------|--------|---------|
| TrueCodeLab | Synced (1 list: "Доска задач") | 9014579452 |
| Yerevan Mall | Not connected | — |
| CubicSoft | Not connected | — |

---

## API Endpoints (17 total)

### Health
- `GET /health` — Service status
- `GET /health/db` — Database connectivity

### Tasks
- `GET /api/v1/tasks` — List tasks (filters: company, status, priority, assignee, overdue, `unresolved_only`, `include_total`)
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

### Webhooks
- `POST /api/v1/webhooks/clickup` — ClickUp webhook endpoint

### Nini Issues
- `GET /api/v1/nini-issues` — List issue backlog entries (filters: status, severity)
- `POST /api/v1/nini-issues` — Create issue backlog entry
- `PATCH /api/v1/nini-issues/{id}` — Update issue status/severity/resolution notes

---

## Key Architectural Decisions

1. **Fetch full task on every webhook** — один код-пасс нормализации, минимум API calls
2. **sync_hash (MD5)** — предотвращает лишние записи и бесконечные циклы двусторонней синхронизации
3. **Dual company resolution** — сначала кастом-поле "Company", потом имя папки как fallback
4. **Dual DB connections** — PgBouncer (port 6543) для API, Direct (port 5432) для sync/migrations
5. **user_id everywhere** — готовность к multi-tenancy
6. **Commit per list** — sync коммитит после каждого списка, чтобы избежать statement_timeout
7. **Skip closed tasks on insert** — задачи с `status_type=closed` не создаются, но обновляются если уже есть
8. **Single-list sync mode** — временно синкается только список `901410057231` ("Доска задач")
9. **Supervisor pattern** — проактивные ритуалы управляются Supervisor, а не простым cron; поддерживает recovery после downtime
10. **Work session anti-spam** — ping cadence контролируется `last_ping_at`, чтобы исключить дубли на 5-минутном цикле
11. **Live data over plan snapshots** — при обсуждении прогресса задач сначала проверяются live статусы через `get_tasks`
12. **Nini issue backlog** — ошибки ассистента логируются в отдельную таблицу и отображаются в dashboard
13. **Telegram HTML strict mode** — запрет markdown `**`; для задач обязательны ссылки `<a href="...">...`

---

## Proactive AI System

### Ритуалы (Asia/Yerevan timezone)

| Время | Ритуал | Recovery до |
|-------|--------|-------------|
| 10:30 | Morning Plan | 14:00 |
| 14:00 | Midday Replan | 18:00 |
| 21:00 | EOD Review | 23:00 |

### Компоненты

- **DailyPlanner** — генерирует структурированные планы через Claude (must_do / should_do / can_wait / blocked)
- **Supervisor** — каждые 5 мин проверяет `DailyState`, запускает ритуалы, обрабатывает recovery
- **AdaptiveMessenger** — выбирает тон (assertive / neutral / casual / soft) на основе контекста; recovery-префиксы чередуются
- **DailyContext** — краткосрочная память дня: активность пользователя, история взаимодействий
- **Work session modes**:
  - idle (без active task): ping каждые 15 мин
  - active task + estimate: checks по estimate/3
  - active task без estimate: checks каждые 5 мин (до получения оценки)

---

## File Structure

```
nini-ai-agent/
├── backend/
│   ├── alembic/                    # DB migrations (10 applied)
│   ├── app/
│   │   ├── main.py                 # FastAPI app + lifespan
│   │   ├── config.py               # pydantic-settings
│   │   ├── database.py             # Dual engines (pooled + direct)
│   │   ├── dependencies.py         # DI (DAVIT_USER_ID)
│   │   ├── models/                 # SQLAlchemy ORM (10 tables)
│   │   │   ├── daily_plan.py       # Morning/midday/EOD plans
│   │   │   ├── daily_state.py      # Ritual execution state per day
│   │   │   ├── daily_context.py    # Short-term daily memory
│   │   │   └── nini_issue.py       # Issue backlog model for Nini mistakes
│   │   ├── schemas/                # Pydantic request/response
│   │   ├── routers/                # health, tasks, projects, sync, webhooks, nini_issues
│   │   ├── services/
│   │   │   ├── clickup/            # client, normalizer, webhook_handler, task_sync
│   │   │   ├── sync_engine.py      # Full sync orchestrator
│   │   │   ├── supervisor.py       # Proactive AI supervisor layer
│   │   │   └── ai/
│   │   │       ├── nini_brain.py   # Claude conversational AI + tools
│   │   │       ├── daily_planner.py # Morning/midday/EOD plan generation
│   │   │       └── adaptive_messenger.py # Context-aware message framing
│   │   ├── core/                   # exceptions, logging
│   │   └── tasks/
│   │       ├── sync_scheduler.py   # Background sync (every 6h)
│   │       └── daily_jobs.py       # Supervisor loop (every 5 min)
│   ├── tests/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env
├── frontend/                       # React Telegram Mini App
├── docker-compose.dev.yml
├── PROJECT_STATUS.md
└── TODO.md
```
