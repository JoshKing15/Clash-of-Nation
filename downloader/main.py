"""Optional Clash of Nations social-video downloader. Deploy on a server, not static hosting."""
import asyncio
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

app = FastAPI(title="Clash of Nations Downloader")
origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["POST", "GET"], allow_headers=["Content-Type"])
ALLOWED = ("x.com", "twitter.com", "tiktok.com", "youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com")
MAX_BYTES = 250 * 1024 * 1024

class DownloadRequest(BaseModel):
    url: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/download")
async def download(req: DownloadRequest):
    parsed = urlparse(req.url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or parsed.username or parsed.password or not any(host == h or host.endswith("." + h) for h in ALLOWED):
        raise HTTPException(400, "Only HTTPS links from supported social platforms are allowed.")
    directory = tempfile.TemporaryDirectory(prefix="clash-")
    path = Path(directory.name)
    cmd = ["yt-dlp", "--no-playlist", "--no-config", "--no-progress",
           "--max-filesize", "250M", "--socket-timeout", "15", "--retries", "1",
           "--merge-output-format", "mp4",
           "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
           "-o", str(path / "source.%(ext)s"), req.url]
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise HTTPException(504, "Download timed out.")
        if process.returncode:
            raise HTTPException(422, "Platform could not provide this video. It may require login, be private, or block downloads.")
        outputs = [p for p in path.iterdir() if p.is_file()]
        if not outputs:
            raise HTTPException(422, "No video was downloaded.")
        result = max(outputs, key=lambda p: p.stat().st_size)
        if result.stat().st_size > MAX_BYTES:
            raise HTTPException(413, "Video exceeds 250 MB limit.")
        return FileResponse(result, media_type="video/mp4" if result.suffix == ".mp4" else "application/octet-stream",
                            filename="clash-source" + result.suffix, background=BackgroundTask(directory.cleanup))
    except HTTPException:
        directory.cleanup()
        raise
    except Exception:
        directory.cleanup()
        raise HTTPException(500, "Downloader failed.")
