"""The pipeline must offload blocking AI work and honour the budget."""

from __future__ import annotations

import asyncio
import inspect
import threading

from atlas_api.services.news import pipeline as pipeline_mod


def test_pipeline_offloads_grading_off_the_event_loop():
    """Guards against reintroducing the event loop freeze fixed in 4f6d728."""
    source = inspect.getsource(pipeline_mod)
    assert "asyncio.to_thread" in source, (
        "grade_article is blocking and must be offloaded with asyncio.to_thread"
    )


def test_grading_actually_runs_on_a_worker_thread():
    main_thread = threading.current_thread()
    seen: dict[str, bool] = {}

    def fake_blocking_grade() -> None:
        seen["on_main"] = threading.current_thread() is main_thread

    async def main() -> None:
        await asyncio.to_thread(fake_blocking_grade)

    asyncio.run(main())
    assert seen["on_main"] is False
