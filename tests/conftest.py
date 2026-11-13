"""Shared fixtures.

Set CLASH_ROOT to test a different checkout (for example a worktree of `main`)
with the exact same tests: CLASH_ROOT=/path/to/tree pytest
"""
import functools
import http.server
import importlib.util
import os
import pathlib
import socketserver
import subprocess
import sys
import threading

import pytest

ROOT = pathlib.Path(os.environ.get("CLASH_ROOT") or pathlib.Path(__file__).resolve().parents[1]).resolve()


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    """Small synthetic media generated locally; nothing third-party is used."""
    d = tmp_path_factory.mktemp("media")
    quad = ("color=c=black:s=640x360:r=30:d=30,"
            "drawbox=x=0:y=0:w=320:h=180:color=red:t=fill,"
            "drawbox=x=320:y=0:w=320:h=180:color=lime:t=fill,"
            "drawbox=x=0:y=180:w=320:h=180:color=blue:t=fill,"
            "drawbox=x=320:y=180:w=320:h=180:color=yellow:t=fill")
    # Quadrant video with SILENT audio: any sound in an export is an effect sound.
    _ffmpeg("-f", "lavfi", "-i", quad, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "quad.mp4"))
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=660:duration=1", str(d / "beep.wav"))
    return {"quad": d / "quad.mp4", "beep": d / "beep.wav", "dir": d}


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def site():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(ROOT)))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


@pytest.fixture(scope="session")
def _playwright():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(_playwright):
    b = _playwright.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    yield b
    b.close()


IPHONE = {"width": 430, "height": 932}


@pytest.fixture
def make_page(browser, site):
    contexts = []

    def _make(viewport=None, mobile=True, goto=True):
        ctx = browser.new_context(viewport=viewport or IPHONE, device_scale_factor=2,
                                  is_mobile=mobile, has_touch=mobile)
        contexts.append(ctx)
        ctx.route(lambda u: not (u.startswith("http://127.0.0.1") or u.startswith("blob:") or u.startswith("data:")),
                  lambda r: r.abort())
        page = ctx.new_page()
        page.js_errors = []
        page.on("pageerror", lambda e: page.js_errors.append(str(e)))
        if goto:
            page.goto(site)
        return page

    yield _make
    for c in contexts:
        c.close()


@pytest.fixture
def page(make_page):
    p = make_page()
    yield p
    assert not p.js_errors, "uncaught JavaScript errors: %s" % p.js_errors


def load_video(page, path):
    page.set_input_files("#file", str(path))
    page.wait_for_function("loaded === true", timeout=15000)


@pytest.fixture
def loaded_page(page, media):
    load_video(page, media["quad"])
    return page


def _import_backend():
    spec = importlib.util.spec_from_file_location("clash_backend_under_test", ROOT / "backend" / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def backend(monkeypatch):
    """Import a fresh copy of backend/app.py (under CLASH_ROOT) with the given env vars set for the whole test."""
    for key in ("GROQ_API_KEY", "FRONTEND_ORIGIN", "ALLOW_LOCALHOST_DEV", "MAX_CONCURRENT_JOBS", "RATE_LIMIT_PER_MINUTE"):
        monkeypatch.delenv(key, raising=False)

    def _load(env=None):
        for key, value in (env or {}).items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        return _import_backend()

    return _load