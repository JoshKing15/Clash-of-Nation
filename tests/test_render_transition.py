"""Command-level regression tests; no media fixtures or FFmpeg required."""
from backend.render_transition import build_render_command


def test_fade_audio_video_overlap_and_output():
    command = build_render_command("source.mp4", "out.mp4", 2, 7, 10, 20, .6, "fade")
    graph = command[command.index("-filter_complex") + 1]
    assert "offset=4.400" in graph
    assert "acrossfade=d=0.600" in graph
    assert "duration=0.600" in graph
    assert command[command.index("-t") + 1] == "14.400"
    assert command[-1] == "out.mp4"


def test_cut_does_not_insert_silence():
    command = build_render_command("source.mp4", "out.mp4", 2, 7, 10, 20, .6, "cut")
    graph = command[command.index("-filter_complex") + 1]
    assert "[v0][v1]concat=n=2:v=1:a=0[vout]" in graph
    assert "[a0][a1]concat=n=2:v=0:a=1[aout]" in graph
    assert "acrossfade" not in graph
