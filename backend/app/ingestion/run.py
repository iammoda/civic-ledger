from __future__ import annotations

import argparse
import asyncio

from app.ingestion.openparliament import OpenParliamentClient


async def run_sync(mode: str) -> None:
    client = OpenParliamentClient()
    if mode == "full":
        await client.paginate("/politicians/")
    else:
        await client.paginate("/votes/", params={"limit": 20})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ingestion jobs")
    parser.add_argument("--full", action="store_true", help="Run a full sync")
    parser.add_argument("--incremental", action="store_true", help="Run an incremental sync")
    args = parser.parse_args()
    mode = "full" if args.full else "incremental"
    asyncio.run(run_sync(mode))


if __name__ == "__main__":
    main()
