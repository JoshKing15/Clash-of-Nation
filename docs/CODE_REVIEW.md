# Code review: Clash of Nations (Nov 2026)

Scope: `index.html`, `backend/app.py`, ffmpeg processing, meme/sound catalogues. Every defect below was reproduced
(by a failing automated test on `main`, or by direct measurement) before it was fixed.
Result: **57 of 110 tests fail on `main`; all 110 pass on this branch** (3 consecutive runs, headless Chromium).

## Prioritized bug report

### High
| # | Defect | Fix |
|---|--------|-----|
| H1 | yt-dlp could use its generic extractor: arbitrary URLs and redirects were fetched *before* the post-download extractor check. | `allowed_extractors` allow-list; `fb.watch` (generic-only) is resolved by hand, every hop validated (allow-list + public IP). |
| H2 | DNS lookup ran on the event loop; unbounded parallel ffmpeg jobs on a 512 MB host; no rate limit. | Worker-thread validation, job slots (503 when busy), per-visitor limit (429). |
| H3 | Raw exception text returned to clients (ffmpeg command lines, temp paths). | Fixed, user-safe messages; details logged server-side only. |
| H4 | Caption endpoint turned deliberate 503 into 502 "503: ..."; client `platform` text pasted into the LLM prompt. | Status preserved; platform allow-listed. |
| H5 | Live crop preview was stretched (`object-fit: fill`) and mispositioned for any crop not centred. | Contain-fit, correct transform, clipped to the exported frame. |
| H6 | Pixelated mask + crop pixelated the wrong source region in the export. | Mask mapped through the crop rectangle. |
| H7 | Failed direct links were saved to "recent links"; double-tap started two downloads. | Remembered only after the video loads; import guarded. |
| H8 | Auto memes fired on common words ("what", "how", "stop"), picked the first hits instead of the best, and had no sensitive-content guard despite `docs/EFFECTS_LIBRARY.md`. | Scored classifier, best-moments selection, 6 max / 2.5 s apart, sensitive moments skipped. |

### Medium
| # | Defect | Fix |
|---|--------|-----|
| M1 | Backend HTML error pages surfaced as "Unexpected token '<'"; no timeout for a sleeping Render instance; HTTPS enforced for only some calls. | One `apiJson` helper: timeout, readable messages, HTTPS everywhere. |
| M2 | Transcription/censoring re-read the whole video from its blob URL (2x memory on iPhone). | Upload the picked `File` directly. |
| M3 | Effect sound window 0.15 s: missed whenever timers lag (phones). Overlapping effects drew one picture but played two sounds. | 0.35 s window; overlaps trimmed. |
| M4 | Only the first 180 s were transcribed, silently. | Backend reports `truncated`; UI says so. |
| M5 | Uploads rejected by exact MIME (`video/x-m4v`, `video/3gpp`, `;codecs=`). | Any `video/*`; ffmpeg decides. |
| M6 | Audio import: extension fallback regex matched a literal backslash, so files with an empty MIME type were refused. | Fixed (`isAudioFile`). |
| M7 | Swear-word beeps duplicated on repeat runs. | Ranges merged. |
| M8 | Drew every 10 ms (~100/s) for a 30 fps recording; export bitrate fixed at 6.5 Mbps whatever the length (whole recording held in memory). | Draw ≤32/s; `planExport` lowers bitrate or refuses clips that cannot fit. |
| M9 | Imported pictures kept at full size (4096² = 64 MB decoded). | Downscaled to 1024 px. |
| M10 | CORS accepted one origin only, no local-dev option. | Comma list + `ALLOW_LOCALHOST_DEV`. |

### Low
- Six tabs wrapped onto two rows (grid had 5 columns): 148 px to 79 px.
- A stray `}` made browsers discard a whole `@media` block (it never applied); removed with no visual change.
- Instagram links were treated as direct files in the UI though the backend supports them.
- Catalogue vocabulary (`shock`, `confusion`, `surprise`) did not match app ids; SVGs had no intrinsic size.
- Catalogue links could carry non-http(s) schemes; failed built-in graphics were silent.
- Unsupported browsers (< iOS 15.4) got a blank page; they now get a notice.
- GIF import was rejected; now accepted as first frame.
- API docs exposed by default; now opt-in.

## Requirements preserved (and guarded by tests)
Six tabs; two independently scrolling panels with visible, draggable rails; recent-link history (5, newest first);
catalogue links never treated as media files; no third-party media bundled.

## Remaining limitations (not verified or not done)
1. **No real iPhone/Safari testing was possible.** Only Chromium ran. Untested: MediaRecorder pause/resume sync on Safari, drawing from a `display:none` video, AudioContext resume rules, memory ceilings.
2. Animated GIFs and short MP4 reaction clips are **not supported** (first frame only; no clip overlay). Adding clip overlay needs a second decoder and memory budget; recommended as a separate, device-tested change.
3. The library bundles only six original graphics and three synthesized tones. Catalogue entries are links; nothing was link-checked (no network). Emoji in exports use the device's emoji font.
4. Cloud analysis is limited to 80 MB uploads and the first 180 s. A 4K phone clip will usually exceed that.
5. Reaction choice is English keyword scoring, not understanding. The sensitive-topic list is conservative and English-only; always review the preview.
6. `fb.watch` resolution and yt-dlp extraction were tested with mocks, not live platforms.
7. `Dockerfile` still runs as root and was not changed (image could not be built here). `downloader/` is an older, divergent copy of the API without these protections: delete it or align it.
8. Per-visitor limits rely on `TRUST_FORWARDED_FOR=1` behind Render; verify after deploy. Security headers (CSP) should be set on the static host.
9. README's hosted-editor link points at a different domain than `render.yaml`; confirm which is current.