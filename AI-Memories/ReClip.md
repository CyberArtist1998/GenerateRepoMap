# ReClip Media Downloader - Operations Guide

## Project Location
- **Root:** `D:\MyWorld-Sync\012-Utility\Reclip`
- **App:** `D:/MyWorld-Sync/012-Utility/Reclip/app/app.py`
- **Venv:** `D:/MyWorld-Sync/012-Utility/Reclip/app/env/Scripts/python.exe` (MUST use this, NOT Hermes venv)

## Quick Start
```bash
cd "D:/MyWorld-Sync/012-Utility/Reclip/app" && env/Scripts/python.exe app.py
# Server runs on http://127.0.0.1:8899
```

## Download a Video (API Workflow)

### Step 1: Get video info
```bash
curl -s -X POST "http://127.0.0.1:8899/api/info" \
  -H "Content-Type: application/json" \
  -d '{"url": "<YOUTUBE_URL>"}'
```

### Step 2: Start download
```bash
curl -s -X POST "http://127.0.0.1:8899/api/download" \
  -H "Content-Type: application/json" \
  -d '{"url": "<YOUTUBE_URL>", "format": "video", "format_id": "299"}'
# Returns: {"job_id": "..."}
```

### Step 3: Check status
```bash
curl -s "http://127.0.0.1:8899/api/status/<JOB_ID>"
# Status values: downloading, completed, failed
```

## Format Options (YouTube)
| ID | Label | Quality |
|----|-------|---------|
| 299 | 1080p | Best video |
| 298 | 720p | HD |
| 135 | 480p | SD |
| 18 | 360p | Low |

## Proxy Configuration
- Auto-detects Windows proxy from registry (`HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings`)
- Falls back to `HTTP_PROXY`/`HTTPS_PROXY` environment variables
- Current proxy: `http://127.0.0.1:10808`

## Important Notes
- ALWAYS use the project venv Python, never Hermes agent's Python
- Proxy must be active for YouTube access from Iran
- If download fails with SSL error, check proxy is actually running
- Downloaded files go to: `D:\MyWorld-Sync\012-Utility\Reclip\app\downloads\`

## Common Commands
```bash
# Check if server is running
curl -s "http://127.0.0.1:8899/" | head -5

# Test proxy connectivity
curl -s --proxy http://127.0.0.1:10808 "https://www.google.com" -o nul -w "%{http_code}"
```
