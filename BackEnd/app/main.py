"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import CORS_ORIGINS
from app.db import create_tables, SessionLocal
from app.seed import seed_database

from app.api.routes_auth import router as auth_router
from app.api.routes_spots import router as spots_router
from app.api.routes_explore import router as explore_router
from app.api.routes_drill import router as drill_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_analytics import router as analytics_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables and seed data."""
    logger.info("Starting PokerTrainer backend...")
    create_tables()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    logger.info("Backend ready.")
    yield


app = FastAPI(
    title="PokerTrainer API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth_router)
app.include_router(spots_router)
app.include_router(explore_router)
app.include_router(drill_router)
app.include_router(jobs_router)
app.include_router(analytics_router)


@app.get("/")
def root():
    return {"service": "PokerTrainer API", "status": "ok"}
