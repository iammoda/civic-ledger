"""Refresh the local Registry of Lobbyists export ZIP.

Cloudflare on lobbycanada.gc.ca binds cf_clearance to the TLS fingerprint
of the session that solved the challenge, so external HTTP clients get
403 even with the right cookies + UA. The reliable Option A: run
Playwright, let Chrome pass the challenge, then download the ZIP inside
the same page via fetch() — same TLS session, cleanly passes.

Usage:
  PYTHONPATH=backend .venv/bin/python scripts/refresh_lobby_export.py
"""
from __future__ import annotations

import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, "backend")

from app.core.config import get_settings  # noqa: E402

# patchright's fingerprint patches let the Cloudflare challenge complete.
try:
    from patchright.sync_api import sync_playwright  # type: ignore
except ImportError:  # pragma: no cover
    from playwright.sync_api import sync_playwright  # type: ignore

OPEN_DATA_URL = "https://lobbycanada.gc.ca/en/open-data/"
ZIP_PATH = "/media/mqbbmaqk/communications_ocl_cal.zip"


def main() -> int:
    settings = get_settings()
    imports_dir = Path(settings.imports_dir)
    imports_dir.mkdir(parents=True, exist_ok=True)
    zip_path = imports_dir / "communications_ocl_cal.zip"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(locale="en-CA")
        page = context.new_page()
        try:
            page.goto(OPEN_DATA_URL, wait_until="load", timeout=120_000)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED: could not reach open-data page: {exc}", file=sys.stderr)
            browser.close()
            return 1

        for _ in range(60):
            if "Just a moment" not in (page.title() or ""):
                break
            time.sleep(1)
        if "Just a moment" in (page.title() or ""):
            print("FAILED: Cloudflare challenge did not clear", file=sys.stderr)
            browser.close()
            return 1

        # In-page fetch: same TLS session that solved the challenge.
        # (context.request goes out on a different TLS stack — 403.)
        result = page.evaluate(
            """
            async (path) => {
              const r = await fetch(path, { credentials: 'include' });
              if (r.status !== 200) return { status: r.status };
              const buf = new Uint8Array(await r.arrayBuffer());
              let bin = '';
              for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
              return { status: 200, b64: btoa(bin), size: buf.length };
            }
            """,
            ZIP_PATH,
        )
        browser.close()

    if result.get("status") != 200:
        print(f"FAILED: in-page fetch returned {result.get('status')}", file=sys.stderr)
        return 1
    data = base64.b64decode(result["b64"])
    if data[:2] != b"PK":
        print("FAILED: response was not a ZIP file", file=sys.stderr)
        return 1
    zip_path.write_bytes(data)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"OK: saved {zip_path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
