"""Clash of Nations: bounded social-video import API for authorized videos."""
import asyncio
import ipaddress
import os
import pathlib
import socket
import tempfile
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

app = FastAPI(title="Clash of Nations Downloader", version="0.1.0")
allowed_origin = os.getenv("FRONTEND_ORIGIN", "https://clash-of-nation-1.onrender.com").rstrip("/")
app.add_middleware(CORSMiddleware, allow_origins=[allowed_origin], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
HOSTS = ("x.com", "twitter.com", "tiktok.com", "youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com")
MAX_BYTES = 80 * 1024 * 1024

class DownloadRequest(BaseModel):
    url: str

@app.get("/health")
async def health():
    return {"status": "ok"}

def validate_url(raw: str):
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Only public HTTPS video-post links are supported")
    if not any(host == d or host.endswith("." + d) for d in HOSTS):
        raise ValueError("Unsupported video host")
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Video host must resolve to a public IP address")
    except socket.gaierror:
        raise ValueError("Video host could not be resolved")
    return raw

def download(raw: str, folder: str):
    import yt_dlp
    # yt-dlp may follow platform redirects; restrict the extractor to supported platforms.
    options = {
        "outtmpl": str(pathlib.Path(folder) / "video.%(ext)s"),
        "format": "best[ext=mp4][height<=720]/best[height<=720]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "max_filesize": MAX_BYTES,
        "socket_timeout": 12,
        "retries": 1,
        "fragment_retries": 1,
        "extractor_retries": 1,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "playlistend": 1,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(raw, download=True)
        if not info or info.get("is_live"):
            raise ValueError("Video unavailable or live streams are not supported")
        extractor = (info.get("extractor_key") or "").lower()
        if not any(x in extractor for x in ("twitter", "tiktok", "youtube", "facebook", "instagram")):
            raise ValueError("Unsupported media extractor")
    candidates = [p for p in pathlib.Path(folder).iterdir() if p.suffix.lower() in (".mp4", ".webm", ".mov", ".mkv")]
    if not candidates:
        raise ValueError("No downloadable video was returned")
    chosen = max(candidates, key=lambda p: p.stat().st_size)
    if chosen.stat().st_size > MAX_BYTES:
        raise ValueError("Video exceeds the 80 MB limit")
    # Normalize to MP4 for iOS Safari.
    target = pathlib.Path(folder) / "output.mp4"
    import subprocess
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(chosen),
                    "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
                    "-preset", "ultrafast", "-crf", "28", "-c:a", "aac",
                    "-movflags", "+faststart", str(target)], timeout=100, check=True)
    if not target.exists() or not target.stat().st_size or target.stat().st_size > MAX_BYTES:
        raise ValueError("Video conversion failed or exceeded size limit")
    return str(target)

@app.post("/api/download")
async def api_download(request: DownloadRequest):
    try:
        url = validate_url(request.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    folder = tempfile.TemporaryDirectory(prefix="clash-")
    try:
        path = await asyncio.wait_for(asyncio.to_thread(download, url, folder.name), timeout=140)
        return FileResponse(path, media_type="video/mp4", filename="clash-source.mp4",
                            background=BackgroundTask(folder.cleanup))
    except Exception as exc:
        folder.cleanup()
        # Platform restrictions, private videos and rate limits may prevent retrieval.
        raise HTTPException(status_code=422, detail=f"Video could not be retrieved: {str(exc)[:180]}")
