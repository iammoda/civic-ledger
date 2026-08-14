"""Error reporting: Sentry, wired only when SENTRY_DSN is set.

One init shared by the API process and the arq worker. Without a DSN this
is a no-op — dev and self-hosters run clean with zero external calls.
"""
from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def init_sentry(*, process: str) -> None:
    settings = get_settings()
    dsn = settings.sentry_dsn
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.app_env,
            # Errors always; keep transaction sampling light — this platform
            # is budget-capped everywhere else too.
            traces_sample_rate=0.05,
            # Anonymous platform: never attach request bodies or user context.
            send_default_pii=False,
        )
        sentry_sdk.set_tag("process", process)
        logger.info("Sentry enabled (%s, env=%s)", process, settings.app_env)
    except Exception:  # pragma: no cover — reporting must never take the app down
        logger.exception("Sentry init failed; continuing without error reporting")
