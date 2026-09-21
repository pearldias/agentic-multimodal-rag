# import logging
# from contextlib import asynccontextmanager
# from fastapi import FastAPI
# from backend.app.api.routes.health import router as health_router
# from backend.app.core.config import settings
# from backend.app.core.logging import setup_logging

# logger = logging.getLogger(__name__)


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Application lifespan manager to configure logging and lifecycle events."""
#     setup_logging()
#     logger.info(
#         "Starting %s (v%s) in [%s] environment",
#         settings.PROJECT_NAME,
#         settings.VERSION,
#         settings.ENVIRONMENT,
#     )
#     yield
#     logger.info("Stopping %s", settings.PROJECT_NAME)


# app = FastAPI(
#     title=settings.PROJECT_NAME,
#     version=settings.VERSION,
#     lifespan=lifespan,
#     debug=settings.DEBUG,
# )

# # Register routers
# app.include_router(health_router)

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from backend.app.api.routes.upload import router as upload_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.conversations import router as conversations_router
from backend.app.api.routes.health import router as health_router
from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.db.database import init_db
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to configure logging, DB schema, and lifecycle events."""

    setup_logging()

    logger.info(
        "Starting %s (v%s) in [%s] environment",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.ENVIRONMENT,
    )

    # Initialize SQLite tables and WAL mode
    init_db()

    yield

    logger.info("Stopping %s", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(upload_router)