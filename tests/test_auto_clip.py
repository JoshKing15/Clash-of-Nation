"""Regression tests for transcript-guided highlight suggestions."""
import pytest
from fastapi.testclient import TestClient

from backend.auto_clip import propose_clips, valid_segments


def sample_segments():
    return [
        {"from": 1, "to": 4, "text": "We are starting the discussion"},
        {"from": 6, "to": 10, "text": "Wait, why did that happen?"},
        {"from": 40, "to": 44, "text": "Listen! That is wrong."},
        {"from": 48, "to": 51, "text": "Can you explain what happened?"},
        {"from": 75, "to": 79, "text": "The final answer is actually different."},
    ]


def test_suggestions_within_source_and_non_redundant():
    clips = propose_clips(sample_segments(), 90, length=20, count=3)
    assert 1 <= len(clips) <= 3
    for clip in clips:
        assert 0 <= clip["from"] < clip["to"] <= 90
        assert "excerpt" in clip
    for i, a in enumerate(clips):
        for b in clips[i+1:]:
            assert min(a["to"], b["to"]) - max(a["from"], b["from"]) <= 5


def test_empty_transcript_and_invalid_input():
    assert propose_clips([], 30) == []
    with pytest.raises(ValueError):
        propose_clips([{"from": -1, "to": 3, "text": "bad"}], 30)
    with pytest.raises(ValueError):
        propose_clips([{"from": 1, "to": 2, "text": "x" * 251}], 30)
    with pytest.raises(ValueError):
        propose_clips([], float("nan"))
    with pytest.raises(ValueError):
        propose_clips([], 30, length=1)


def test_rate_limited_highlight_endpoint(backend):
    module = backend({"RATE_LIMIT_PER_MINUTE": "1"})
    client = TestClient(module.app)
    payload = {"duration": 90, "length": 20, "segments": sample_segments()}
    success = client.post("/api/auto-clips", json=payload)
    assert success.status_code == 200
    assert success.json()["selection_method"] == "transcript_heuristic"
    assert success.json()["clips"]
    assert client.post("/api/auto-clips", json=payload).status_code == 429


def test_highlight_api_rejects_invalid_timestamps(backend):
    module = backend()
    payload = {"duration": 30, "segments": [{"from": -1, "to": 4, "text": "test"}]}
    response = TestClient(module.app).post("/api/auto-clips", json=payload)
    assert response.status_code == 422


def test_ui_contains_review_controls(root):
    html = (root / "index.html").read_text()
    assert 'id="suggestHighlights"' in html
    assert "showHighlightChoices" in html
    assert "Use this highlight" in html
    assert "byId('start').value" in html
