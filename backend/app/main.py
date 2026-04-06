import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import NiniError
from app.core.logging import setup_logging
from app.routers import health, projects, sync, tasks, webhooks
from app.tasks.sync_scheduler import periodic_full_sync

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Nini backend starting up (env=%s)", settings.app_env)
    # Start background sync scheduler
    sync_task = asyncio.create_task(periodic_full_sync())
    yield
    sync_task.cancel()
    logger.info("Nini backend shutting down")


app = FastAPI(
    title="Nini AI Project Manager",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Telegram Mini App and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_dev else [settings.webhook_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NiniError)
async def nini_error_handler(request: Request, exc: NiniError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )


# Routers
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(sync.router)
app.include_router(webhooks.router)
