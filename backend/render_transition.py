"""Bounded FFmpeg export endpoint for a teaser and main excerpt.

No client-side overlays are silently discarded: this is a separate opt-in
render endpoint until full feature parity is implemented.
"""
import asyncio
import pathlib
import subprocess
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .transition_plan import plan_transition

router = APIRouter()


def build_render_command(source: str, destination: str, teaser_start: float,
                         teaser_end: float, main_start: float, main_end: float,
                         overlap: float, mode: str):
    teaser_length = teaser_end - teaser_start
    main_length = main_end - main_start
    plan = plan_transition(teaser_length, main_length, overlap, mode)
    # Normalize each excerpt before the transition; xfade requires identical
    # dimensions, frame rate, pixel format and time base.
    graph = (
        f"[0:v]trim=start={teaser_start:.3f}:end={teaser_end:.3f},"
        "setpts=PTS-STARTPTS,fps=30,scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,format=yuv420p,"
        "settb=AVTB[v0];"
        f"[0:v]trim=start={main_start:.3f}:end={main_end:.3f},"
        "setpts=PTS-STARTPTS,fps=30,scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,format=yuv420p,"
        "settb=AVTB[v1];"
        f"[0:a]atrim=start={teaser_start:.3f}:end={teaser_end:.3f},"
        "asetpts=PTS-STARTPTS,aresample=48000,"
        "aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
        f"[0:a]atrim=start={main_start:.3f}:end={main_end:.3f},"
        "asetpts=PTS-STARTPTS,aresample=48000,"
        "aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
    )
    if mode == "fade":
        graph += (f"[v0][v1]xfade=transition=fade:duration={overlap:.3f}:"
                  f"offset={teaser_length-overlap:.3f}[vout];"
                  f"[a0][a1]acrossfade=d={overlap:.3f}:c1=tri:c2=tri[aout]")
    else:
        graph += ("[v0][v1]concat=n=2:v=1:a=0[vout];"
                  "[a0][a1]concat=n=2:v=0:a=1[aout]")
    return [
        "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
        "-i", source, "-filter_complex", graph,
        "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        "-t", f"{plan.output_duration:.3f}", destination,
    ]


def run_render(command):
    return subprocess.run(command, capture_output=True, text=True, timeout=110, check=False)


@router.post("/api/render-transition")
async def render_transition(
    file: UploadFile = File(...),
    teaser_start: float = Form(...), teaser_end: float = Form(...),
    main_start: float = Form(...), main_end: float = Form(...),
    overlap: float = Form(0.6), mode: str = Form("fade"),
):
    from .app import JOBS, MAX_BYTES, busy
    import math
    values = (teaser_start, teaser_end, main_start, main_end, overlap)
    if any(not math.isfinite(x) for x in values):
        raise HTTPException(422, "Invalid timing")
    if not (0 <= teaser_start < teaser_end <= 120 and
            0 <= main_start < main_end <= 120 and
            main_end - main_start + teaser_end - teaser_start <= 120):
        raise HTTPException(422, "Clips must be within the first 120 seconds and total at most 120 seconds")
    try:
        plan_transition(teaser_end-teaser_start, main_end-main_start, overlap, mode)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not (file.content_type or "").startswith("video/") and file.content_type != "application/octet-stream":
        raise HTTPException(400, "Upload a video file")
    folder = tempfile.TemporaryDirectory(prefix="clash-render-")
    source = str(pathlib.Path(folder.name) / "source.mp4")
    destination = str(pathlib.Path(folder.name) / "render.mp4")
    worker_started = False
    try:
        size = 0
        with open(source, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "Video exceeds 80 MB")
                output.write(chunk)
        if not size:
            raise HTTPException(400, "Empty video")
        if not JOBS.try_acquire():
            raise busy()
        worker_started = True
        command = build_render_command(source, destination, teaser_start, teaser_end,
                                       main_start, main_end, overlap, mode)
        def work():
            try:
                return run_render(command)
            finally:
                JOBS.release()
        # Shield the thread so cancellation doesn't release its concurrency slot.
        task = asyncio.create_task(asyncio.to_thread(work))
        try:
            result = await asyncio.wait_for(asyncio.shield(task), timeout=115)
        except asyncio.TimeoutError:
            task.add_done_callback(lambda _: folder.cleanup())
            raise HTTPException(504, "Rendering timed out")
        except asyncio.CancelledError:
            task.add_done_callback(lambda _: folder.cleanup())
            raise
        if result.returncode or not pathlib.Path(destination).is_file():
            raise HTTPException(422, "Could not render this clip; ensure the source has an audio track")
        return FileResponse(destination, media_type="video/mp4",
                            filename="clash-transition.mp4",
                            background=BackgroundTask(folder.cleanup))
    except BaseException:
        if not worker_started:
            folder.cleanup()
        elif 'task' in locals() and task.done():
            folder.cleanup()
        raise
