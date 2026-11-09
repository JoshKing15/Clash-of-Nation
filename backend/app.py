"""Clash of Nations: bounded social-video import API for authorized videos."""
import asyncio
import ipaddress
import os
import pathlib
import socket
import tempfile
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, UploadFile, File
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

# Reviewable, English-language profanity suggestions. Never auto-apply without review.
PROFANITY = {"fuck","fucking","fucked","fucker","motherfucker","shit","shitty","bullshit","bitch","bitches","asshole","assholes","cunt","dick","cock","pussy","bastard","wanker","twat"}

def transcribe_audio(video_path: str, audio_path: str):
    import subprocess
    subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-i",video_path,
                    "-vn","-ac","1","-ar","16000","-b:a","48k","-t","180",audio_path],
                   check=True,timeout=45)
    if pathlib.Path(audio_path).stat().st_size > 24*1024*1024:
        raise ValueError("Audio is too large for transcription")
    import httpx
    with open(audio_path,"rb") as audio:
        response = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization":"Bearer "+os.environ["GROQ_API_KEY"]},
            data={"model":"whisper-large-v3-turbo","response_format":"verbose_json",
                  "timestamp_granularities[]":"word"},
            files={"file":("audio.mp3",audio,"audio/mpeg")},timeout=100)
    if response.status_code != 200:
        raise ValueError("Cloud transcription failed (HTTP "+str(response.status_code)+")")
    words = response.json().get("words",[])
    result = []
    import re
    for word in words:
        raw = str(word.get("word","")).strip()
        clean = re.sub(r"[^a-z]","",raw.lower())
        if clean in PROFANITY:
            start = max(0,float(word.get("start",0))-.08)
            end = max(start+.12,float(word.get("end",start+.3))+.08)
            result.append({"word":raw,"from":round(start,2),"to":round(end,2),"mode":"bleep"})
    return {"suggestions":result,"words_analyzed":len(words)}

@app.post("/api/detect-profanity")
async def detect_profanity(file: UploadFile = File(...)):
    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(status_code=503,detail="Add GROQ_API_KEY to the Render backend environment to enable AI detection.")
    if file.content_type not in ("video/mp4","video/webm","video/quicktime","application/octet-stream"):
        raise HTTPException(status_code=400,detail="Upload an MP4, WebM or MOV video.")
    with tempfile.TemporaryDirectory(prefix="clash-ai-") as folder:
        video_path = str(pathlib.Path(folder)/"source.mp4")
        size=0
        with open(video_path,"wb") as output:
            while chunk := await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_BYTES:
                    raise HTTPException(status_code=413,detail="Video exceeds 80 MB.")
                output.write(chunk)
        if not size:
            raise HTTPException(status_code=400,detail="Empty video.")
        try:
            return await asyncio.wait_for(asyncio.to_thread(
                transcribe_audio,video_path,str(pathlib.Path(folder)/"audio.mp3")),timeout=145)
        except Exception as exc:
            raise HTTPException(status_code=422,detail=str(exc)[:220])
