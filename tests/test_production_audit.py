"""Production audit regressions: reject uploads before parsing and retain worker slots."""
import asyncio
import threading
import time

from fastapi.testclient import TestClient


def test_rejects_oversized_content_length_before_reading(backend):
    mod = backend({"GROQ_API_KEY": "dummy", "RATE_LIMIT_PER_MINUTE": "0"})
    with TestClient(mod.app) as client:
        response = client.post("/api/detect-profanity", data=b"x", headers={
            "content-type": "multipart/form-data; boundary=x",
            "content-length": str(mod.MAX_BYTES + 2 * 1024 * 1024),
        })
    assert response.status_code == 413


def test_rate_limit_rejects_before_multipart_parsing(backend):
    mod = backend({"GROQ_API_KEY": "dummy", "RATE_LIMIT_PER_MINUTE": "1"})
    with TestClient(mod.app) as client:
        first = client.post("/api/detect-profanity", data=b"invalid", headers={"content-type": "multipart/form-data; boundary=x"})
        second = client.post("/api/detect-profanity", data=b"invalid", headers={"content-type": "multipart/form-data; boundary=x"})
    assert first.status_code != 429
    assert second.status_code == 429


def test_timeout_does_not_release_active_worker_slot(backend, monkeypatch):
    mod = backend({"GROQ_API_KEY": "dummy", "MAX_CONCURRENT_JOBS": "1", "RATE_LIMIT_PER_MINUTE": "0"})
    started = threading.Event()
    finish = threading.Event()
    def slow_work(video, audio):
        started.set()
        finish.wait(5)
        return {"segments": []}
    monkeypatch.setattr(mod, "transcribe_audio", slow_work)
    real_wait_for = asyncio.wait_for
    async def short_wait_for(awaitable, timeout):
        return await real_wait_for(awaitable, timeout=0.05)
    monkeypatch.setattr(mod.asyncio, "wait_for", short_wait_for)
    try:
        with TestClient(mod.app) as client:
            response = client.post("/api/detect-profanity", files={"file": ("clip.mp4", b"1234", "video/mp4")})
            assert response.status_code == 504
            assert started.is_set()
            assert not mod.JOBS.try_acquire(), "timed-out worker must retain its slot"
    finally:
        finish.set()
    for _ in range(100):
        if mod.JOBS.try_acquire():
            mod.JOBS.release()
            break
        time.sleep(0.01)
    else:
        assert False, "worker did not release its slot after exiting"
