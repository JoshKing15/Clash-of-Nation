"""Regression tests for synchronized teaser transitions."""
import pytest

from backend.transition_plan import plan_transition


def test_fade_uses_same_overlap_for_audio_and_video():
    plan = plan_transition(5, 12, 0.6)
    assert "offset=4.400" in plan.filter_complex
    assert "duration=0.600" in plan.filter_complex
    assert "acrossfade=d=0.600" in plan.filter_complex
    assert plan.output_duration == pytest.approx(16.4)


def test_hard_cut_has_no_added_silence():
    plan = plan_transition(5, 12, mode="cut")
    assert "concat=n=2:v=0:a=1" in plan.filter_complex
    assert "acrossfade" not in plan.filter_complex
    assert plan.output_duration == 17


@pytest.mark.parametrize("args", [(1, 2, 1), (0, 2, .5), (2, 2, float("nan"))])
def test_invalid_overlap_rejected(args):
    with pytest.raises(ValueError):
        plan_transition(*args)
