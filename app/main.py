import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.anthropic_proxy import router as anthropic_proxy_router
from app.api.dashboard import router as dashboard_router
from app.api.openai_proxy import router as openai_proxy_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

app = FastAPI(title=settings.project_name)
app.include_router(openai_proxy_router)
app.include_router(anthropic_proxy_router)
app.include_router(dashboard_router)

frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/dashboard", StaticFiles(directory=frontend_dist, html=True), name="dashboard")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}