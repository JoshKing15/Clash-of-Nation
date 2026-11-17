# AI Auto-Clip — phase 1 (transcript-driven suggestions)

This is an **opt-in editor helper**, not a standalone video rendering engine or a copy of OpusClip. No OpusClip or other third-party source code is included.

## How to use

1. Load an authorized video into Clash of Nations.
2. Open **Subtitles**, choose **Auto Transcribe Speech** (requires configured Groq cloud transcription).
3. Choose **Find 3 Highlight Clips**. The backend evaluates a bounded set of time-stamped transcript windows and returns up to three suggestions.
4. Review the text and timestamps. Select **Use this highlight** to populate the existing Start/End controls.
5. Inspect the actual video. Optionally add a teaser, censorship, subtitle styles, logo, or effects; use the existing preview/export path.

Selecting a suggestion turns off any previously selected teaser so you don't accidentally export an unrelated old teaser. The user can re-enable and configure a teaser manually.

## API

`POST /api/auto-clips` JSON body: `{"duration":90,"length":30,"count":3,"segments":[{"from":5,"to":8,"text":"Wait, why did that happen?"}]}`.

Returns `clips`, `selection_method: transcript_heuristic`, and a cautionary note.

No new API key is required for ranking. Suggestions are based on transcribed speech activity, questions, and emphasis. They do **not** predict virality or establish whether a disputed claim is true. The existing optional cloud transcription already processes video with a cloud provider; the highlight endpoint itself only receives timestamped transcript text, not video files.

Limits: up to 300 segments, 250 characters each, source duration <= 7200 seconds, requested clips 10–60 seconds, 1–3 suggestions.

## Next phases

- LLM-assisted story/scene ranking and timestamped multi-part clips.
- Speaker changes, scene cuts, face tracking, automatic 9:16 reframing.
- Confidence, full-speech context, human review and disinformation safeguards.
- Streaming job progress and actual device tests.
- Full-feature FFmpeg export parity is tracked separately in PR #4 and roadmap issue #6.

**Release gate:** tests and an end-to-end browser review before merge/deployment.
