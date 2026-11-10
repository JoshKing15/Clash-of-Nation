# Phase 6 — AI Sound Effects & Meme Moments

Status: **planned; no application implementation yet**.

## Objective
Help creators add appropriate reaction sounds and meme overlays at meaningful moments in an edited clip. AI **suggests**; the creator must **approve** every insertion.

## Prerequisites
- Phase 2: one shared preview/export frame geometry for crops, overlays, and subtitles.
- Phase 5: a single transcription endpoint returning word timestamps, with reliable cut-relative timing.
- Confirm browser and export audio mixing on an actual iPhone before release.

## Proposed workflow
1. Transcribe the clip with word-level timestamps.
2. Analyze audio loudness peaks and silences, preferably locally in the browser. Send bounded, coarse event timings and transcript to the backend.
3. POST /api/suggest-moments: return at most eight candidates with timestamp, category, effect kind (sound/meme/both), catalogue asset ID, and short rationale. Validate suggestions against a fixed asset manifest; never let model output supply arbitrary URLs or file paths.
4. Present suggestions in an **Effects** tab (sixth tab). Each has Preview, Swap, Move, Remove, and Approve controls. Nothing is added until approved.
5. Preview and Export use the same approved effect timeline. Audio effects mix with the existing audio graph; image overlays use the same canvas coordinate system as watermark, mask, and subtitles. Provide volume, position, size, and duration controls.

## API design (proposal)
- POST /api/suggest-moments
  - Request: transcript words/segments, selected cut boundaries, bounded loudness/silence event list, optional tone setting.
  - Response: suggestions [{time_seconds, kind, category, asset_id, reason}].
  - Validate maximum request sizes, asset IDs, timestamps and categories server-side. Enforce existing planned authentication, rate limits, and concurrency limits.
  - Allowed categories initially: shock, fail, awkward_silence, dramatic_reveal. Expand only after evaluation.
- No server-side asset downloads from model output.

## Assets and licensing
- `assets/sfx/` — approved short audio files.
- `assets/memes/` — approved original or licensed image overlays.
- `assets/effects-manifest.json` — stable ID, file path, type, attribution, source, licence, verification date, and any usage restrictions.
- Only add an asset after reviewing licence terms for social publishing and monetization. Publicly viewable is not equivalent to reusable. Avoid copying recognizable copyrighted meme audio (including the referenced “fahhh” sound); commission/record original alternatives or use verified suitable licences.
- Load only approved/selected assets on iPhone; avoid preloading the entire catalogue.

## Sensitive footage guard
- Default to **no comedic suggestions** for clips depicting or discussing real injury, death, violence, tragedy or vulnerable people.
- Require an explicit per-clip opt-in to see effect suggestions for flagged material; do not override platform rules or creator judgement.
- Prefer non-mocking, informational treatment when context is uncertain.

## Compatibility guardrails
- Keep both independent mobile scroll panes and both visible scrollbar rails.
- Preserve the five existing tabs and their IDs; add Effects as a sixth tab.
- Keep five-link recent history and existing crop, watermark, subtitles, profanity censor, and caption behavior.
- Preserve timing across teaser, cut, transitions, pause/resume and export.
- Store effect selections with future per-video draft settings, not just in volatile page state.

## Acceptance tests
- iPhone Safari, iOS Chrome/in-app browser, desktop Chrome.
- Transcript timings map correctly to both main cut and teaser.
- No suggestions are applied without approval; Remove fully removes the asset.
- Preview/export show identical meme placement and timing; audio remains synchronized.
- Repeated exports do not duplicate sounds or leak audio nodes.
- Sensitive footage produces no comedic suggestions by default.
- Unsupported/unknown asset IDs are rejected.
- Scroll panes and draggable rails still work independently.
- Test memory with multiple suggestions and a long portrait video.

## Rollout
1. Manifest schema and small licence-reviewed starter library.
2. Manual effects placement with preview/export parity.
3. Transcript-driven suggestion endpoint and review UI.
4. Optional visual moment detection only after verifying access to a suitable vision model and explicit consent for sampled frames.

## Decisions still needed
- Approve initial sound and original meme catalogue.
- Decide whether sensitive-content opt-in should permit all effects or only neutral effects.
- Confirm iPhone device test results before enabling automatic suggestions in production.
