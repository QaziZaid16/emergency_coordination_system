import asyncio

import pytest

from app import intelligence, main
from app.config import Settings


def test_development_lifespan_starts_one_worker_and_cancels_it_on_shutdown(
    monkeypatch,
):
    started = asyncio.Event()
    stopped = asyncio.Event()
    calls = []
    schema_calls = []

    async def worker():
        calls.append("started")
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(main, "settings", Settings(environment="development"))
    monkeypatch.setattr(
        main.Base.metadata,
        "create_all",
        lambda bind: schema_calls.append(bind),
    )
    monkeypatch.setattr(main, "run_analysis_recovery_worker", worker)

    async def exercise_lifespan():
        async with main.lifespan(main.app):
            await asyncio.wait_for(started.wait(), timeout=2)
            assert calls == ["started"]
        assert stopped.is_set()

    asyncio.run(exercise_lifespan())

    assert len(schema_calls) == 1


def test_test_environment_does_not_start_polling_worker(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "settings", Settings(environment="test"))
    monkeypatch.setattr(main.Base.metadata, "create_all", lambda bind: None)

    async def worker():
        calls.append("started")

    monkeypatch.setattr(main, "run_analysis_recovery_worker", worker)

    async def exercise_lifespan():
        async with main.lifespan(main.app):
            await asyncio.sleep(0)

    asyncio.run(exercise_lifespan())
    assert calls == []


def test_polling_loop_survives_iteration_errors_and_propagates_shutdown(
    monkeypatch,
):
    poll_calls = []
    analyzed = []
    sleep_calls = []

    def next_job():
        poll_calls.append(len(poll_calls) + 1)
        if len(poll_calls) in (2, 3):
            raise RuntimeError("synthetic isolated database iteration failure")
        return "synthetic-incident" if len(poll_calls) == 1 else None

    async def isolated_to_thread(function):
        return function()

    async def isolated_sleep(_seconds):
        sleep_calls.append(None)
        if len(sleep_calls) == 4:
            raise asyncio.CancelledError

    async def fake_analysis(incident_id):
        analyzed.append(incident_id)

    monkeypatch.setattr(intelligence, "next_pending_analysis_job", next_job)
    monkeypatch.setattr(intelligence.asyncio, "to_thread", isolated_to_thread)
    monkeypatch.setattr(intelligence.asyncio, "sleep", isolated_sleep)
    monkeypatch.setattr(intelligence, "analyze_incident_task", fake_analysis)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(intelligence.run_analysis_recovery_worker())

    assert len(poll_calls) == 5
    assert analyzed == ["synthetic-incident"]
    assert len(sleep_calls) == 4
