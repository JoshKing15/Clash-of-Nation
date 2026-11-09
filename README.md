# Clash-of-Nation

Browser-based clip editor for Clash of Nations videos. Trim a clip, add an optional teaser, and bleep or mute selected sections.

Open the [hosted editor](https://clash-of-nations-clip-editor.nicesheep16.chatgpt.site) in Safari or run `python -m http.server 8000` from this folder and open `http://localhost:8000`.

Import a video from Photos or Files, or use a direct HTTPS media link with cross-origin access enabled. For social posts, use the platform’s download or export option when available and import the saved file.

Under **Import from a direct video link**, paste the URL or choose a text file containing the URL. If the file has several links, the editor uses the first. Select **Download original**, then **Save original video** to save the source video without editing it.

Use Watermarks to add the Clash of Nations logo or pixelate or cover a fixed rectangle over an existing mark. Preview the result, then select Export video. The editor prefers MP4 when the browser supports it. On supported phones, Save / Share opens the system share sheet. Download saves the file directly.
