"""FFmpeg filter graph for gap-free teaser/main video and audio transitions.

This is a pure planning helper. It does not alter the existing browser exporter.
The caller must provide two normalized inputs with video and audio streams.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TransitionPlan:
    filter_complex: str
    video_label: str = "[vout]"
    audio_label: str = "[aout]"
    output_duration: float = 0.0


def plan_transition(teaser_duration: float, main_duration: float,
                    overlap: float = 0.6, mode: str = "fade") -> TransitionPlan:
    """Plan one synchronized transition; durations are seconds.

    Inputs must have matching resolution, frame rate, pixel format, time base,
    sample rate, and channel layout. Normalize upstream with FFmpeg filters.
    """
    for value in (teaser_duration, main_duration, overlap):
        if not isinstance(value, (int, float)) or not 0 < value < float("inf"):
            raise ValueError("Durations and overlap must be finite positive numbers")
    if mode not in ("fade", "cut"):
        raise ValueError("Unsupported transition")
    if mode == "fade" and overlap >= min(teaser_duration, main_duration):
        raise ValueError("Overlap must be shorter than both clips")
    if mode == "cut":
        graph = (
            "[0:v]setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];"
            "[0:a]asetpts=PTS-STARTPTS[a0];[1:a]asetpts=PTS-STARTPTS[a1];"
            "[v0][v1]concat=n=2:v=1:a=0[vout];"
            "[a0][a1]concat=n=2:v=0:a=1[aout]"
        )
        return TransitionPlan(graph, output_duration=teaser_duration + main_duration)
    # xfade offset and acrossfade duration refer to the exact same overlap.
    graph = (
        "[0:v]setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];"
        "[0:a]asetpts=PTS-STARTPTS[a0];[1:a]asetpts=PTS-STARTPTS[a1];"
        f"[v0][v1]xfade=transition=fade:duration={overlap:.3f}:"
        f"offset={teaser_duration-overlap:.3f}[vout];"
        f"[a0][a1]acrossfade=d={overlap:.3f}:c1=tri:c2=tri[aout]"
    )
    return TransitionPlan(graph, output_duration=teaser_duration + main_duration - overlap)
