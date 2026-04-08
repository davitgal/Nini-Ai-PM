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
- [x] Work session ping logic refined:
  - idle mode (без active task): пинги каждые 15 мин
  - active task + estimate: checks по схеме estimate/3
  - active task без estimate: checks каждые 5 мин
  - anti-spam guard через `last_ping_at` чтобы не дублировать пинги на 5-минутном supervisor loop
- [x] Context switch protocol: если пользователь сообщил, что фактически работал над другой задачей — закрыть старую сессию и перезапустить flow для новой
- [x] Live-status priority rule: выводы по выполнению задач делаются после проверки `get_tasks`, а не только по `daily_plan`
- [x] Response formatting hard rules: только Telegram HTML, запрет markdown `**`, обязательные task links через `<a href="...">`
- [x] Self-issue logging tool (`log_issue`) для фиксации ошибок Нини в backlog

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
- [x] React Telegram Mini App
- [x] Overview Dashboard с Nini Issues Backlog (создание/просмотр/смена статуса issues)
- [x] Убраны нерелевантные блоки "По компаниям" и "По статусам" из Overview
- [x] Исправлен crash/black screen на Overview (React hooks mismatch)
- [x] Оптимизация скорости загрузки Overview:
  - отключён тяжёлый total count для коротких списков (`include_total=false`)
  - server-side фильтр unresolved tasks (`unresolved_only=true`)
  - убран блокирующий fullscreen loader, добавлены query cache настройки
- [ ] Task board view (kanban by company/priority)
- [ ] Calendar view (deadlines, milestones)
- [ ] Analytics dashboard
- [ ] Deploy to Vercel

### Backlog
- [ ] AI priority scoring (nini_priority на основе контекста задачи)
- [ ] "Большая уборка" — онбординг для ревью всех задач
- [ ] Workload analysis по компаниям
- [ ] Webhook health monitoring
- [ ] Автоприменение Alembic migrations на deploy (чтобы новые таблицы не требовали ручного SQL)
