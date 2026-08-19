# Telegram Gateway Proxy Fix - Session Report

**Date:** 2026-07-29  
**Status:** ✅ Resolved

---

## Problem
Telegram gateway was failing to connect with repeated timeouts:
```
[Telegram] Primary api.telegram.org connection failed (All connection attempts failed)
[Telegram] Fallback IP 149.154.166.110 failed: Timed out
```

Root cause: Hermes Telegram platform does not automatically inherit Windows system proxy settings, and the user is in Iran where direct Telegram access requires a proxy.

## Solution Applied

### 1. Added Proxy to `.env` File
File: `C:\Users\RedRain2077\AppData\Local\hermes\.env`

```
HTTPS_PROXY=http://127.0.0.1:10808
HTTP_PROXY=http://127.0.0.1:10808
```

### 2. Added Proxy to `config.yaml` (backup)
File: `C:\Users\RedRain2077\AppData\Local\hermes\config.yaml`

```yaml
platforms:
  telegram:
    enabled: true
    proxy: http://127.0.0.1:10808
env:
  HTTPS_PROXY: http://127.0.0.1:10808
  HTTP_PROXY: http://127.0.0.1:10808
```

### 3. Restarted Gateway
Gateway successfully connected via proxy:
```
[Telegram] Proxy detected; passing explicitly to HTTPXRequest: http://127.0.0.1:10808
[Telegram] Connected to Telegram (polling mode)
✓ telegram connected
```

## Key Learnings

1. **Hermes reads proxy from `.env` file**, not Windows registry or system settings
2. The `platforms.telegram.proxy` config key may not be implemented in all versions — environment variables are more reliable
3. Gateway must be restarted after adding `.env` entries for changes to take effect
4. System proxy at `127.0.0.1:10808` is a SOCKS proxy (likely from VPN/proxy software)

## Current Configuration

- **Proxy:** `http://127.0.0.1:10808`
- **Telegram Bot:** Connected via polling mode
- **Webhook:** Listening on port 8644
- **Model:** qwen3.6-35b-a3b (LM Studio at http://127.0.0.1:1234)
- **Platform:** Telegram + Webhook

## Files Modified

| File | Changes |
|------|---------|
| `C:\Users\RedRain2077\AppData\Local\hermes\.env` | Added HTTPS_PROXY, HTTP_PROXY |
| `C:\Users\RedRain2077\AppData\Local\hermes\config.yaml` | Added platforms.telegram.proxy, env section |

## Verification Commands

```bash
# Check gateway status
hermes gateway status

# View recent logs
tail -n 30 "C:/Users/RedRain2077/AppData/Local/hermes/logs/gateway.log"

# Test proxy connectivity
python -c "import requests; print(requests.get('https://api.telegram.org', timeout=5).status_code)"
```

## Notes for Future

- If Telegram connection fails again, check that the proxy at `127.0.0.1:10808` is still active
- The `.env` file takes precedence over config.yaml for proxy settings
- Gateway process runs as a background service (Windows login item installed)
- To restart gateway from outside the running session, use terminal directly
