from __future__ import annotations

import asyncio
import signal


async def run_worker() -> None:
    stop_event = asyncio.Event()

    def _handle_stop(*_: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    await stop_event.wait()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
