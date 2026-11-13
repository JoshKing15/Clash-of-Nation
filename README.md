# Clash-of-Nation

Browser-based clip editor for Clash of Nations videos. Trim a clip, add an optional teaser, and bleep or mute selected sections.

Open the [hosted editor](https://clash-of-nations-clip-editor.nicesheep16.chatgpt.site) in Safari or run `python -m http.server 8000` from this folder and open `http://localhost:8000`.

Import a video from Photos or Files, or use a direct HTTPS media link with cross-origin access enabled. For social posts, use the platform’s download or export option when available and import the saved file.

Under **Import from a direct video link**, paste the URL or choose a text file containing the URL. If the file has several links, the editor uses the first. Select **Download original**, then **Save original video** to save the source video without editing it.

Use Watermarks to add the Clash of Nations logo or pixelate or cover a fixed rectangle over an existing mark. Preview the result, then select Export video. The editor prefers MP4 when the browser supports it. On supported phones, Save / Share opens the system share sheet. Download saves the file directly.


## Tests

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium   # one-off; also needs ffmpeg on PATH
python -m pytest                        # backend + real-browser tests, generated media only
CLASH_ROOT=/path/to/other/checkout python -m pytest   # run the same tests against another tree
```

Browser tests run in headless Chromium. They cannot prove iPhone Safari behaviour; see `docs/CODE_REVIEW.md`.

## Backend settings (environment variables)

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | Cloud transcription and captions (never commit it). |
| `FRONTEND_ORIGIN` | Allowed editor origin(s), comma-separated. |
| `ALLOW_LOCALHOST_DEV=1` | Also allow `http://localhost:*` (local development only). |
| `MAX_CONCURRENT_JOBS` | Parallel ffmpeg jobs; extra requests get 503 (default 2, Render free: 1). |
| `RATE_LIMIT_PER_MINUTE` | Per-visitor request limit (default 20, `0` disables). |
| `TRUST_FORWARDED_FOR=1` | Use the proxy-supplied client address for rate limits (set on Render). |
| `ENABLE_DOCS=1` | Expose `/docs` (off by default). |

Browsers need iOS / Safari 15.4 or newer; older ones see a notice instead of a broken page.