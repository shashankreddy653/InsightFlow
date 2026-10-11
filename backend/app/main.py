"""InsightFlow FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import analytics, feedback, issues, reports, system

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("insightflow")

settings = get_settings()

app = FastAPI(
    title="InsightFlow API",
    description="Intelligent Customer Feedback & Decision Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    logger.info("InsightFlow backend started; database initialized.")


@app.get("/api/ping")
def ping():
    return {"pong": True}


app.include_router(system.router)
app.include_router(feedback.router)
app.include_router(analytics.router)
app.include_router(issues.router)
app.include_router(reports.router)
