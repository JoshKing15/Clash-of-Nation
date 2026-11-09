# Optional social video downloader

This is a **server-side** yt-dlp service for the static Clash of Nations editor. It cannot run on GitHub Pages or inside Safari.

Deploy the Dockerfile in this folder to a container host with persistent compute (e.g. Render or Railway). Set `ALLOWED_ORIGINS` to the exact hosted editor origin, such as `https://clash-of-nations-clip-editor.nicesheep16.chatgpt.site`. HTTPS is required for a hosted editor. The server needs outbound network access and ffmpeg.

In the editor, expand **Import from a direct video link**, enter your public backend HTTPS URL in **Video downloader API URL**, paste the X/TikTok/YouTube/Facebook post URL, and select **Import** or **Download original**. A text file containing a link also works.

Check `GET /health` on the backend after deployment. A public post may still fail due to login, age, regional, DRM or anti-bot restrictions. The service does not bypass access restrictions. Download and edit only content you have rights to use.

Security: configure restrictive CORS, add authentication and rate limits before exposing to the public, and enforce network egress restrictions to prevent abuse. This sample imposes a 120-second timeout and a 250 MB file cap. For production, add concurrency controls and reverse-proxy request limits.
