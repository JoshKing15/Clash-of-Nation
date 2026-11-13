import base64
import json
import subprocess

import numpy as np

API = "https://clash-of-nation.onrender.com"
CORS = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "GET,POST,OPTIONS"}


def mock_api(page, path, status=200, body=None, content_type="application/json", raw=None, calls=None, hang=False):
    """Intercept one backend endpoint (CORS preflight included) and record calls."""
    def handler(route):
        req = route.request
        if req.method == "OPTIONS":
            return route.fulfill(status=204, headers=CORS)
        if calls is not None:
            calls.append(req)
        if hang:
            return  # never answer: simulates a stalled Render cold start
        payload = raw if raw is not None else json.dumps(body if body is not None else {}).encode()
        route.fulfill(status=status, body=payload, headers={**CORS, "content-type": content_type})
    page.route(API + path, handler)


def pixel_class(rgb):
    palette = {"red": (255, 0, 0), "lime": (0, 255, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0), "black": (0, 0, 0)}
    return min(palette, key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb[:3], palette[k])))


def quadrant_color(u, v):
    return {(0, 0): "red", (1, 0): "lime", (0, 1): "blue", (1, 1): "yellow"}[(int(u >= .5), int(v >= .5))]


def set_segments(page, items):
    page.evaluate("items=>{subtitleSegments.length=0;items.forEach(i=>subtitleSegments.push(i));renderSubtitleRows();}", items)


def effects(page):
    return page.evaluate("reactionEffects.map(e=>({from:e.from,duration:e.duration,sound:e.sound,text:e.text,"
                         "id:(e.imageName||'').split(' ')[0],auto:!!e.autoMeme}))")


def export_to_file(page, path):
    page.click("#export")
    page.wait_for_selector("#download:not([hidden])", timeout=60000)
    data = page.evaluate("""async()=>{const b=await (await fetch(download.href)).blob();const a=new Uint8Array(await b.arrayBuffer());
      let s='';for(let i=0;i<a.length;i+=0x8000)s+=String.fromCharCode(...a.subarray(i,i+0x8000));return btoa(s)}""")
    open(path, "wb").write(base64.b64decode(data))
    return path


def audio_onset(path, thr=0.01):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32)
    w = 320
    n = len(a) // w
    rms = np.sqrt((a[:n * w].reshape(n, w) ** 2).mean(axis=1))
    hits = np.nonzero(rms > thr)[0]
    return None if not len(hits) else hits[0] * 0.02


def video_onset(path, threshold=40):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-an", "-vf", "fps=30,scale=64:36",
                          "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 36, 64, 3).astype(int)
    base = f[0, 12:24, 24:40].mean(axis=(0, 1))
    for i, fr in enumerate(f):
        if np.abs(fr[12:24, 24:40].mean(axis=(0, 1)) - base).sum() > threshold:
            return i / 30
    return None