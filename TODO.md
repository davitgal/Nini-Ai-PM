# Nini AI Agent — TODO

## Phase 1: Backend Core + ClickUp Sync

### Done
- [x] Project scaffolding (monorepo, pyproject.toml, Makefile, Docker)
- [x] Config + DB setup (pydantic-settings, async SQLAlchemy, Alembic)
- [x] FastAPI skeleton (app factory, health, CORS, error handling, DI)
- [x] Database schema (6 tables: users, workspaces, projects, unified_tasks, sync_log, knowledge_base)
- [x] ClickUp REST client (async httpx, rate limiter 100 req/min, retry on 429/5xx)
- [x] Task normalizer (ClickUp JSON -> unified_tasks, company_tag resolution, sync_hash)
- [x] Full sync engine (spaces -> folders -> lists -> tasks, commit per list)
- [x] Webhook receiver (signature verification, idempotency, event routing)
- [x] Outbound sync (push to ClickUp, conflict detection via date_updated)
- [x] REST API endpoints (14 endpoints: tasks CRUD, projects, sync, stats)
- [x] Background sync scheduler (every 6 hours)
- [x] Unit tests (7 normalizer tests passing)
- [x] First full sync: 1,049 tasks from TrueCodeLab synced to Supabase
- [x] DB reset + clean re-sync with new logic
- [x] Skip closed tasks on insert (status_type=closed → не создаём, но обновляем если есть)
- [x] Single-list sync mode: только "Доска задач" (list_id: 901410057231) в scheduler и UI
- [x] Reconciliation fix: при single-list sync архивируем только задачи этого листа

### Remaining
- [ ] Расширить sync на все листы (убрать DEV_SYNC_LIST_ID когда будет готово)
- [ ] Connect Yerevan Mall workspace (need team_id + API token)
- [ ] Connect CubicSoft workspace (need team_id + API token)
- [ ] Register ClickUp webhooks for real-time sync
- [ ] Git init + initial commit

---

## Phase 2: Telegram Bot + Claude AI  <-- NEXT

### Telegram Bot
- [ ] Create Telegram bot via @BotFather
- [ ] Set up bot framework (aiogram or python-telegram-bot)
- [ ] Basic command handlers (/start, /help, /tasks, /status)
- [ ] Connect bot to FastAPI backend
- [ ] Message routing: user message -> Nini AI -> response

### Claude AI Integration
- [ ] Anthropic API client setup
- [ ] System prompt: Nini's personality (Armenian PM assistant, strict but caring)
- [ ] Tool definitions for Claude (get_tasks, create_task, update_task, get_stats)
- [ ] Priority engine: Money > Stakeholders > Deadlines
- [ ] Context building: inject relevant tasks into conversation
- [ ] Natural language task creation ("create a task for Yerevan Mall...")
- [ ] Daily/weekly summary generation

### Conversation Features
- [ ] Ask about tasks ("what's overdue?", "what should I focus on?")
- [ ] Create tasks via natural language
- [ ] Update task status through chat
- [ ] Get priority recommendations
- [ ] Morning briefing (auto-send daily summary)

---

## Phase 3: Smart Features

- [ ] AI priority scoring (nini_priority based on task context)
- [ ] "Great Cleanup" — interactive onboarding to review all tasks
- [ ] Deadline risk detection (flag tasks likely to miss deadlines)
- [ ] Workload analysis across companies
- [ ] Knowledge base (RAG) for project context
- [ ] Smart notifications (Telegram alerts for important changes)

---

## Phase 4: Frontend Dashboard

- [ ] React app (Telegram Mini App)
- [ ] Task board view (kanban by company/priority)
- [ ] Calendar view (deadlines, milestones)
- [ ] Analytics dashboard (company stats, velocity)
- [ ] Deploy to Vercel

---

## Backlog

- [ ] Multi-workspace sync (run parallel syncs)
- [ ] Conflict resolution UI
- [ ] Task dependencies visualization
- [ ] Time tracking integration
- [ ] Custom notification rules
- [ ] Webhook health monitoring
- [ ] API rate limit dashboard
