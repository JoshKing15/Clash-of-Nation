"""Synthetic-media regression tests for the decoded export inspector."""
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inspect_export", ROOT / "tools" / "inspect_export.py")
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_generated_portrait_mp4_has_expected_metadata(tmp_path):
    output = tmp_path / "portrait.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=360x640:r=30:d=2", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=44100:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(output)
    ], check=True, timeout=30)
    report = inspector.inspect(output)
    assert report["width"] == 360
    assert report["height"] == 640
    assert report["video_codec"] == "h264"
    assert report["audio_codec"] == "aac"
    assert report["duration_seconds"] > 1.5
    assert any("below 720" in warning for warning in report["warnings"])


def test_missing_file_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspector.inspect(tmp_path / "missing.mp4")
