"""Video import (files, direct links, social posts), backend error handling, link history."""
import json

import pytest

from conftest import load_video
from helpers import API, mock_api

LINKS_KEY = "clash-of-nations-recent-links-v1"
CORS = {"access-control-allow-origin": "*"}


def route_media(page, url, path, status=200):
    body = open(path, "rb").read()
    page.route(url, lambda r: r.fulfill(status=status, body=body if status == 200 else b"", headers={**CORS, "content-type": "video/mp4"}))


def stored_links(page):
    return json.loads(page.evaluate(f"localStorage.getItem('{LINKS_KEY}') || '[]'"))


def submit_link(page, url):
    page.evaluate("u=>{byId('importPanel').open=true;byId('videoUrl').value=u;byId('importLink').requestSubmit();}", url)


def test_local_file_import_loads_and_collapses_panel(loaded_page):
    assert loaded_page.evaluate("[loaded, video.duration > 29, byId('importPanel').open]") == [True, True, False]


def test_direct_link_is_remembered_after_it_loads(page, media):
    route_media(page, "https://media.example/clip.mp4", media["quad"])
    submit_link(page, "https://media.example/clip.mp4")
    page.wait_for_function("loaded === true")
    assert stored_links(page) == ["https://media.example/clip.mp4"]
    assert "downloaded" not in page.inner_text("#linkStatus").lower()  # it is streamed, not downloaded


def test_failed_direct_link_is_not_remembered(page, media):
    route_media(page, "https://media.example/missing.mp4", media["quad"], status=404)
    submit_link(page, "https://media.example/missing.mp4")
    page.wait_for_function("/could not|unable|failed/i.test(byId('status').textContent)", timeout=10000)
    assert stored_links(page) == []


def test_recent_links_keep_five_newest_first_without_duplicates(page):
    page.evaluate("""()=>{for(const n of [1,2,3,4,5,6,2])rememberVideoLink('https://h.example/v'+n+'.mp4')}""")
    assert stored_links(page) == ["https://h.example/v2.mp4", "https://h.example/v6.mp4", "https://h.example/v5.mp4",
                                  "https://h.example/v4.mp4", "https://h.example/v3.mp4"]
    assert page.locator("#recentLinksList .recent-link-row").count() == 5
    page.evaluate("byId('importPanel').open=true;byId('importPanel').querySelector('details').open=true;byId('recentLinksPanel').open=true")
    page.locator("#recentLinksList .recent-link-row button").first.click()
    assert page.input_value("#videoUrl") == "https://h.example/v2.mp4"


@pytest.mark.parametrize("url,expected", [
    ("https://www.instagram.com/reel/abc/", True),
    ("https://fb.watch/abc/", True),
    ("https://x.com/a/status/1", True),
    ("https://www.tiktok.com/@a/video/1", True),
    ("https://cdn.example/clip.mp4", False),
    ("https://x.com/video.mp4", False),
])
def test_social_links_go_through_the_downloader(page, url, expected):
    assert page.evaluate("u=>isSocialPost(new URL(u))", url) is expected


def test_social_import_is_not_started_twice_and_loads(page, media):
    calls = []
    body = open(media["quad"], "rb").read()
    mock_api(page, "/api/download", raw=body, content_type="video/mp4", calls=calls)
    mock_api(page, "/api/source-caption", status=404, body={"detail": "nope"})
    page.evaluate("()=>{byId('importPanel').open=true;byId('videoUrl').value='https://x.com/a/status/1';"
                  "const f=byId('importLink');f.requestSubmit();f.requestSubmit();}")
    page.wait_for_function("loaded === true", timeout=15000)
    assert len(calls) == 1, "a double tap started %d downloads" % len(calls)
    assert stored_links(page) == ["https://x.com/a/status/1"]


@pytest.mark.parametrize("trigger,path,setup", [
    ("#transcribeSubtitles", "/api/transcribe-subtitles", None),
    ("#autoCensor", "/api/detect-profanity", None),
    ("#generateCaption", "/api/generate-caption", "byId('sourceCaption').value='A debate took place'"),
])
def test_backend_html_errors_become_readable_messages(loaded_page, trigger, path, setup):
    page = loaded_page
    mock_api(page, path, status=502, raw=b"<html><body>Bad gateway</body></html>", content_type="text/html")
    if setup:
        page.evaluate(setup)
    page.evaluate("t=>{document.querySelector(t).click()}", trigger)
    target = {"#transcribeSubtitles": "subtitleStatus", "#autoCensor": "aiStatus", "#generateCaption": "captionStatus"}[trigger]
    page.wait_for_function("id=>!/^(Transcribing|Sending|Generating)/.test(byId(id).textContent)", arg=target, timeout=10000)
    text = page.inner_text("#" + target)
    assert "Unexpected" not in text and "<" not in text and "JSON" not in text, text
    assert any(w in text.lower() for w in ("unavailable", "try again")), text


def test_stalled_backend_times_out_with_a_clear_message(loaded_page):
    page = loaded_page
    mock_api(page, "/api/transcribe-subtitles", hang=True)
    page.evaluate("API_TIMEOUT_MS = 400")
    page.evaluate("document.querySelector('#transcribeSubtitles').click()")
    page.wait_for_timeout(1500)
    assert "too long" in page.inner_text("#subtitleStatus").lower()
    assert page.evaluate("transcribingSubtitles") is False


def test_transcription_uploads_the_picked_file_without_reading_it_back_from_a_blob_url(loaded_page):
    page = loaded_page
    page.evaluate("()=>{window.__fetched=[];const f=window.fetch;window.fetch=(u,...a)=>{window.__fetched.push(String(u&&u.url||u));return f(u,...a)}}")
    mock_api(page, "/api/transcribe-subtitles", body={"segments": [{"from": 0.5, "to": 2, "text": "hello"}]})
    page.evaluate("document.querySelector('#transcribeSubtitles').click()")
    page.wait_for_function("/segments ready/.test(byId('subtitleStatus').textContent)", timeout=10000)
    fetched = page.evaluate("window.__fetched")
    assert not [u for u in fetched if u.startswith("blob:")], "whole video was re-read into memory: %s" % fetched


@pytest.mark.parametrize("trigger", ["#transcribeSubtitles", "#autoCensor", "#generateCaption"])
def test_every_backend_call_requires_https(loaded_page, trigger):
    page = loaded_page
    hosts = []
    page.on("request", lambda r: hosts.append(r.url))
    page.evaluate("()=>{byId('apiUrl').value='http://evil.example';byId('sourceCaption').value='x'}")
    page.evaluate("t=>document.querySelector(t).click()", trigger)
    page.wait_for_timeout(700)
    assert not [u for u in hosts if "evil.example" in u], "sent data to a non-HTTPS backend"
    status = {"#transcribeSubtitles": "subtitleStatus", "#autoCensor": "aiStatus", "#generateCaption": "captionStatus"}[trigger]
    assert "https" in page.inner_text("#" + status).lower()


def test_detected_swear_words_are_merged_not_duplicated(loaded_page):
    page = loaded_page
    mock_api(page, "/api/detect-profanity", body={"suggestions": [
        {"from": 1.0, "to": 1.4, "mode": "bleep"}, {"from": 1.3, "to": 1.8, "mode": "bleep"}, {"from": 5.0, "to": 5.3, "mode": "bleep"}]})
    for _ in range(2):
        page.evaluate("document.querySelector('#autoCensor').click()")
        page.wait_for_function("/possible swear/.test(byId('aiStatus').textContent)")
        page.wait_for_function("!byId('autoCensor').disabled")
    assert page.evaluate("ranges.map(r=>[r.from,r.to])") == [[1.0, 1.8], [5.0, 5.3]]


def test_truncated_transcription_is_reported(loaded_page):
    page = loaded_page
    mock_api(page, "/api/transcribe-subtitles", body={"segments": [{"from": 0.5, "to": 2, "text": "hello"}],
                                                      "truncated": True, "analyzed_seconds": 180})
    page.evaluate("document.querySelector('#transcribeSubtitles').click()")
    page.wait_for_function("/segments ready/.test(byId('subtitleStatus').textContent)")
    text = page.inner_text("#subtitleStatus")
    assert "180" in text and "first" in text.lower()


def test_catalogue_links_cannot_inject_script_urls(page):
    assert page.evaluate("safeHref('javascript:alert(1)')") in ("", None)
    assert page.evaluate("safeHref('https://pixabay.com/x')") == "https://pixabay.com/x"