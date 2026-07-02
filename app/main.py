from fastapi import FastAPI

from app.api.openai_proxy import router as openai_proxy_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title=settings.project_name)
app.include_router(openai_proxy_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

