"""Transcript-guided short-clip recommendations.

The deterministic candidate generator never claims to determine whether an
event occurred or predict virality. Optional cloud AI only reranks candidates.
The user reviews every suggestion before it changes the editor.
"""
import math
import re

SIGNAL_TERMS = frozenset({
    "wait", "stop", "why", "how", "what", "really", "actually", "listen",
    "because", "never", "always", "no", "but", "however", "said",
    "explain", "proof", "truth", "wrong", "agree", "disagree", "question",
    "answer", "look", "happened", "suddenly", "shocked", "surprised",
})
MAX_SEGMENTS = 300
MAX_VIDEO_SECONDS = 7200


def valid_segments(items, duration):
    """Accept only bounded, timestamped captions from the supplied transcript."""
    if not isinstance(items, list) or len(items) > MAX_SEGMENTS:
        raise ValueError("Provide no more than 300 transcript segments")
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 1 <= duration <= MAX_VIDEO_SECONDS:
        raise ValueError("Invalid source duration")
    clean = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid transcript segment")
        start, end, message = item.get("from"), item.get("to"), item.get("text")
        if not isinstance(start, (float, int)) or not isinstance(end, (float, int)):
            raise ValueError("Transcript times must be numeric")
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= duration + 0.1:
            raise ValueError("Invalid transcript segment timing")
        if not isinstance(message, str) or len(message) > 250:
            raise ValueError("Transcript text must contain no more than 250 characters")
        message = " ".join(message.split())
        if message:
            clean.append({"from": float(start), "to": min(float(end), duration), "text": message})
    clean.sort(key=lambda x: x["from"])
    return clean


def propose_clips(items, duration, length=30, count=3):
    """Return diverse candidate cuts ordered by a transparent heuristic.

    Scores are internal ranking signals, not calibrated probabilities.
    """
    clean = valid_segments(items, duration)
    if not isinstance(length, (int, float)) or not math.isfinite(length) or not 10 <= length <= 60:
        raise ValueError("Clip length must be 10 to 60 seconds")
    if not isinstance(count, int) or not 1 <= count <= 3:
        raise ValueError("Choose one to three clips")
    if not clean:
        return []
    length = min(float(length), duration)
    candidates = []
    starts = [0.0]
    starts.extend(max(0.0, min(duration-length, item["from"]-1.5)) for item in clean)
    seen = set()
    for start in starts:
        start = round(start, 2)
        if start in seen:
            continue
        seen.add(start)
        end = min(duration, start + length)
        selected = [x for x in clean if x["to"] > start and x["from"] < end]
        if not selected:
            continue
        words = " ".join(x["text"] for x in selected)
        tokens = re.findall(r"[a-z']+", words.lower())
        signals = sum(t in SIGNAL_TERMS for t in tokens)
        punctuation = sum(x["text"].count("?") + x["text"].count("!") for x in selected)
        speaking = sum(max(0.0, min(end, x["to"])-max(start, x["from"])) for x in selected)
        coverage = min(1, speaking / max(1, end-start))
        # Favour coherent spoken sequences, meaningful dialogue, and questions.
        score = round(5 * coverage + min(4, signals) + min(2, punctuation) + min(3, len(tokens) / 30), 3)
        excerpt = next((x["text"] for x in selected if x["text"].strip()), "")[:140]
        candidates.append({"from": start, "to": round(end, 2), "score": score, "excerpt": excerpt})
    candidates.sort(key=lambda item: (-item["score"], item["from"]))
    chosen = []
    # Most of each suggestion must be unique. Do not suggest the same scene three times.
    for candidate in candidates:
        if any(min(candidate["to"], prev["to"])-max(candidate["from"], prev["from"]) > length * .25 for prev in chosen):
            continue
        chosen.append(candidate)
        if len(chosen) == count:
            break
    return [
        {"id": index+1, "from": entry["from"], "to": entry["to"],
         "excerpt": entry["excerpt"], "reason": "Speech activity and emphasis in the transcript"}
        for index, entry in enumerate(chosen)
    ]
