import logging

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()

# One predictable log format for API + workers; level opens up in dev.
logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Fully anonymous API: no cookies or auth headers cross origins.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Token"],
)
app.include_router(api_router)


@app.get("/health")
def healthcheck(response: Response) -> dict[str, str]:
    """Real dependency check: report degraded (503) if Postgres or Redis is down."""
    checks: dict[str, str] = {}

    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "down"

    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "down"

    healthy = all(status == "ok" for status in checks.values())
    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "degraded", **checks}
