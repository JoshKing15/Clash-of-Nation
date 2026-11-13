# Effects library — sourcing and licence notes

## Currently implemented
- 12 selectable reaction emoji overlays (Unicode characters rendered by the viewer's device font; **not bundled Google Noto artwork**, so appearance can vary by device).
- 3 original synthesized sound stings (boom, scratch, reveal), generated locally with the Web Audio API; no third-party sound files.
- Transcript keyword-based suggestion and explicit per-suggestion approval. This is **not** an AI visual moment detector.
- Text, reaction graphic and sound are included in the canvas/audio preview/export path. Device-level export testing remains pending.

## Candidate libraries for future curated assets
1. **Google Noto Emoji**: https://github.com/googlefonts/noto-emoji — the project's image resources are generally Apache-2.0 and fonts OFL-1.1. Verify each chosen asset's exact licence, retain required notices and bundle a fixed, tested file before claiming a consistent graphic.
2. **Pixabay Sound Effects**: https://pixabay.com/sound-effects/ — https://pixabay.com/service/license-summary/ — Pixabay permits many sound assets to be used in edited commercial videos, but prohibits standalone redistribution and warns about third-party rights. **Do not bulk-copy its sound files into this repository without checking whether redistribution as an app asset library is permitted.** Verify every individual sound and its usage rights.
3. Original recordings or custom synthesized audio are the preferred default for a distributable app sound library.

## Before adding viral meme clips
- Identify original creator/rightsholder and secure an appropriate licence for reproduction, adaptation, commercial video use and redistribution through the editor.
- Record asset ID, source URL, creator, licence, proof/date, restrictions and approved uses.
- Do not imply that a famous viral clip is royalty-free because it is widely shared.
- For footage of real harm, avoid comedic suggestions by default.

## Next engineering steps
- Add a rights-reviewed, pinned static emoji image set (rather than device-font emoji) and tested audio samples where licensing permits bundling.
- Add per-clip sensitive-content controls and context-aware AI suggestion endpoint.
- Test iPhone Safari audio synchronization, emoji export rendering and preview/export parity.


## Behaviour notes (code review, Nov 2026)

- Automatic reactions are scored from the transcript: everyday words like "what" or "how" no longer trigger anything; the strongest moments are chosen, at most 6, at least 2.5 s apart.
- Moments within 8 s of sensitive wording (deaths, shootings, abuse, ...) never receive an automatic comedic reaction. The word list is English-only and deliberately conservative; it does not replace reviewing the preview.
- GIFs can be imported but only their first frame is used. Short MP4 reaction clips are not supported yet; the clip catalogue lists links only and no media file is bundled.
- One reaction is on screen at a time. Adding an overlapping one trims the earlier one, so every picture keeps its own sound.
- Imported pictures are reduced to at most 1024 px to protect phone memory.
- `tests/test_catalogs_and_assets.py` fails if a catalogue entry points at a missing file, if a third-party media file is bundled, or if reaction names drift from the app's own.