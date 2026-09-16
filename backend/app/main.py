import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.app.api.routes.health import router as health_router
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to configure logging and lifecycle events."""
    setup_logging()
    logger.info(
        "Starting %s (v%s) in [%s] environment",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.ENVIRONMENT,
    )
    yield
    logger.info("Stopping %s", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Register routers
app.include_router(health_router)
