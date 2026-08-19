# Findings

_Generated 2026-08-16 03:46 UTC from `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt`_

Classification rule: a hit counts only if it sits inside a control-flow guard
(`if`, `&&`, `?:`, `?.`, early return) or a configuration collection.
String literals, comments, and formatting expressions do not count.

| ok? | file:line | match |
|---|---|---|
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\ARCHITECTURE.md` | `10:- `install.js` (imports 0 files)` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\ARCHITECTURE.md` | `12:- `reset.js` (imports 0 files)` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\ARCHITECTURE.md` | `13:- `start.js` (imports 0 files)` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\ARCHITECTURE.md` | `14:- `update.js` (imports 0 files)` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\graph.json` | `21:      "path": "install.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\graph.json` | `37:      "path": "reset.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\graph.json` | `45:      "path": "start.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\graph.json` | `53:      "path": "update.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\GRAPH.md` | `10:\| `install.js` \| ENTRY \| 0 \| 0 \| 1 \| `(root)` \|` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\GRAPH.md` | `12:\| `reset.js` \| ENTRY \| 0 \| 0 \| 1 \| `(root)` \|` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\GRAPH.md` | `13:\| `start.js` \| ENTRY \| 0 \| 0 \| 1 \| `(root)` \|` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\GRAPH.md` | `14:\| `update.js` \| ENTRY \| 0 \| 0 \| 1 \| `(root)` \|` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\sweep-files.txt` | `10:D:/MyWorld-Sync/012-Utility/Reclip/install.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\sweep-files.txt` | `8:D:/MyWorld-Sync/012-Utility/Reclip/update.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\sweep-ranked.txt` | `10:     1  D:/MyWorld-Sync/012-Utility/Reclip/install.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/.agent\sweep-ranked.txt` | `8:     1  D:/MyWorld-Sync/012-Utility/Reclip/update.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/install.js` | `25:          "uv pip install flask yt-dlp"` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `10:      start: info.running("start.js"),` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `11:      update: info.running("update.js"),` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `12:      reset: info.running("reset.js")` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `19:        href: "install.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `23:        let local = info.local("start.js")` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `33:            href: "start.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `4:  description: "Self-hosted video/audio downloader powered by yt-dlp with a clean web UI.",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `40:            href: "start.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `48:          href: "update.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `55:          href: "reset.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `62:          href: "start.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `66:          href: "update.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `70:          href: "install.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `74:          href: "reset.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `82:        href: "install.js",` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.js` | `9:      install: info.running("install.js"),` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/pinokio.json` | `4:  "description": "Self-hosted, open-source video and audio downloader with a clean web UI. Supports YouTube,` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/README.md` | `14:1. Click **Install** — clones the repo, installs `ffmpeg` via conda, and installs `flask` + `yt-dlp` into` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/README.md` | `3:1-click launcher for [ReClip](https://github.com/averygan/reclip) — a self-hosted, open-source video and a` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt` | `1:yt-dlp` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt` | `2:start.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt` | `3:install.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt` | `4:update.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt` | `5:reset.js` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt` | `6:info.running` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/terms-seed.txt` | `7:info.local` |
| [ ] | `D:/MyWorld-Sync/012-Utility/Reclip/update.js` | `19:        "uv pip install -U flask yt-dlp"` |
