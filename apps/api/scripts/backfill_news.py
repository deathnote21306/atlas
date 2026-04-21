"""One-time backfill: run the news pipeline to populate articles for all countries."""

import asyncio
import sys

sys.path.insert(0, "packages/schemas/src")
sys.path.insert(0, "apps/api/src")


async def main() -> None:
    from atlas_api.services.news.pipeline import run_news_pipeline

    print("Running news pipeline backfill...")
    stats = await run_news_pipeline()
    print(f"Pipeline complete: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
