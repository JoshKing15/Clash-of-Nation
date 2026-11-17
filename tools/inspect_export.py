"""Inspect actual exported video files with ffprobe/ffmpeg (no external API).

Usage: python tools/inspect_export.py clash-of-nations-cut.mp4 --json report.json
Requires ffmpeg and ffprobe installed on PATH.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path


def _run(args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def inspect(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    probe = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    if probe.returncode:
        raise RuntimeError(probe.stderr.strip() or "ffprobe failed")
    meta = json.loads(probe.stdout)
    streams = meta.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise ValueError("No video stream")
    duration = float(meta.get("format", {}).get("duration") or video.get("duration") or 0)
    width, height = int(video["width"]), int(video["height"])
    report = {
        "file": path.name, "duration_seconds": round(duration, 3),
        "size_bytes": path.stat().st_size, "width": width, "height": height,
        "video_codec": video.get("codec_name"), "audio_codec": audio.get("codec_name") if audio else None,
        "frame_rate": video.get("avg_frame_rate"), "warnings": [],
        "silence_intervals": [], "freeze_intervals": [], "black_intervals": [],
    }
    if width < 720:
        report["warnings"].append("Output width below 720 pixels")
    if not audio:
        report["warnings"].append("No audio stream")
    if duration <= 0:
        report["warnings"].append("Missing or invalid duration")
    if duration > 0 and path.stat().st_size / duration < 90000:
        report["warnings"].append("Low average bitrate: inspect compression quality")

    # Limit analysis to first five minutes to avoid unbounded CI processing.
    scan_seconds = min(max(duration, 0), 300)
    if scan_seconds > 0:
        filters = ["freezedetect=n=-50dB:d=1.5", "blackdetect=d=0.5:pix_th=0.10:pic_th=0.98"]
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-t", str(scan_seconds),
               "-i", str(path), "-vf", ",".join(filters)]
        if audio:
            cmd += ["-af", "silencedetect=noise=-40dB:d=0.7"]
        cmd += ["-f", "null", "-"]
        result = _run(cmd, timeout=180)
        log = result.stderr
        def pairs(start_pattern, end_pattern, key):
            starts = [float(x) for x in re.findall(start_pattern, log)]
            ends = [float(x) for x in re.findall(end_pattern, log)]
            report[key] = [{"start": round(a, 2), "end": round(b, 2)}
                           for a, b in zip(starts, ends) if b >= a]
        pairs(r"silence_start:\s*([0-9.]+)", r"silence_end:\s*([0-9.]+)", "silence_intervals")
        pairs(r"freeze_start:\s*([0-9.]+)", r"freeze_end:\s*([0-9.]+)", "freeze_intervals")
        pairs(r"black_start:\s*([0-9.]+)", r"black_end:\s*([0-9.]+)", "black_intervals")
        if result.returncode:
            report["warnings"].append("FFmpeg decoding scan did not complete")
        for key, label in (("silence_intervals", "silence"), ("freeze_intervals", "freeze"), ("black_intervals", "black frames")):
            if report[key]:
                report["warnings"].append(f"Detected {label}; verify whether intentional")
        if duration > 300:
            report["warnings"].append("Only the first 300 seconds were scanned")
    report["limitations"] = ("Black borders, watermark placement, dialogue censoring and audio/video "
                             "lip-sync are not reliably validated by these filters.")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--json", dest="output")
    args = parser.parse_args()
    report = inspect(args.video)
    payload = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
