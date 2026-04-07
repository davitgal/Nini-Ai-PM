# Nini AI Agent — TODO

## Phase 1: Backend Core + ClickUp Sync ✅

- [x] Project scaffolding (monorepo, pyproject.toml, Makefile, Docker)
- [x] Config + DB setup (pydantic-settings, async SQLAlchemy, Alembic)
- [x] FastAPI skeleton (app factory, health, CORS, error handling, DI)
- [x] Database schema (users, workspaces, projects, unified_tasks, sync_log, knowledge_base)
- [x] ClickUp REST client (async httpx, rate limiter 100 req/min, retry on 429/5xx)
- [x] Task normalizer (ClickUp JSON → unified_tasks, company_tag resolution, sync_hash)
- [x] Full sync engine (spaces → folders → lists → tasks, commit per list)
- [x] Webhook receiver (signature verification, idempotency, event routing)
- [x] Outbound sync (push to ClickUp, conflict detection via date_updated)
- [x] REST API endpoints (14 endpoints: tasks CRUD, projects, sync, stats)
- [x] Background sync scheduler (every 6 hours)
- [x] Unit tests (7 normalizer tests passing)
- [x] Skip closed tasks on insert
- [x] Single-list sync mode: только "Доска задач" (list_id: 901410057231)
- [x] Reconciliation fix: архивируем только задачи синкнутого листа

---

## Phase 2: Telegram Bot + Claude AI ✅

- [x] Telegram bot (aiogram 3, long polling, OwnerOnly middleware)
- [x] Commands: /start, /help, /tasks, /overdue, /stats, /briefing, /clear
- [x] Free-text → NiniBrain.chat() → Claude response
- [x] Claude tool use: get_tasks, get_stats, get_overdue_tasks, create_task, update_task, save_memory, delete_memory
- [x] Nini personality: 26-летняя дерзкая PM, говорит по-русски, Telegram HTML formatting
- [x] Auto-sync on user interaction (30-min window)
- [x] Persistent memory via knowledge_base table

---

## Phase 3: Proactive AI ✅

- [x] DailyPlanner: morning plan, midday replan, EOD review через Claude
- [x] DailyPlan модель (must_do / should_do / can_wait / blocked / completed / risks)
- [x] DailyState модель: статус ритуалов на каждый день (pending/done/skipped)
- [x] DailyContext модель: краткосрочная память — активность пользователя, история взаимодействий, риски
- [x] Supervisor: проактивный decision layer (каждые 5 мин, recovery при downtime)
- [x] AdaptiveMessenger: выбор тона (assertive/neutral/casual/soft), ротация recovery-префиксов
- [x] Activity tracking: каждое сообщение пользователя → DailyContext

---

## В работе / Backlog

### ClickUp
- [ ] Расширить sync на все листы (убрать DEV_SYNC_LIST_ID)
- [ ] Connect Yerevan Mall workspace
- [ ] Connect CubicSoft workspace
- [ ] Register ClickUp webhooks для real-time sync

### Proactive AI — следующие шаги
- [ ] Напоминания внутри дня (если есть критические задачи и пользователь неактивен)
- [ ] Контекст из DailyContext в промпты NiniBrain (Нини знает что уже обсуждалось сегодня)
- [ ] Анализ паттернов: "ты обычно продуктивен по утрам, сейчас уже 14:00"

### Phase 4: Frontend Dashboard
- [ ] React Telegram Mini App
- [ ] Task board view (kanban by company/priority)
- [ ] Calendar view (deadlines, milestones)
- [ ] Analytics dashboard
- [ ] Deploy to Vercel

### Backlog
- [ ] AI priority scoring (nini_priority на основе контекста задачи)
- [ ] "Большая уборка" — онбординг для ревью всех задач
- [ ] Workload analysis по компаниям
- [ ] Webhook health monitoring
