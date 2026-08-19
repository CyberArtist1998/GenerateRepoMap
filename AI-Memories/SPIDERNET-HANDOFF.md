# SPIDERNET — Session Handoff / AI Context Pack

> **Read this first, then `SPIDERNET-ROADMAP.md` (same folder).**
> Written to be *digested by an AI agent*: orientation → code map → gotchas → state.
> You do **not** need to read the whole codebase. Section 3 tells you which ~12 files
> matter and how they connect. Everything else is upstream code we don't touch.

Last updated: 2026-07-29

---

## 1. Orientation (read this even if you read nothing else)

**Goal.** A human-in-the-loop OSINT situational-awareness dashboard. Ingest Telegram
channels + multi-language news → a **local LLM (LM Studio)** translates / classifies /
summarizes → events get geolocated and marked on a map. The AI proposes; the operator
judges.

**Base project.** `D:\Mega\031-AI\worldmonitor-main` — a large, mature TS/Vite +
Node dashboard (105 panels, Docker multi-service). We *graft onto* it; we don't rewrite it.

**Donor project.** `D:\Mega\031-AI\Shadowbroker` — an older OSINT dashboard. Parts-only
donor. Its `TODO.md` is superseded. A full Telethon-based Telegram ingestion was built
there and then **sidelined** when we pivoted; the knowledge transferred, the code didn't.

**Operator context (matters for engineering decisions).**
- Windows 11, RTX 4060 **Laptop** (8 GB VRAM), **16 GB RAM single-channel**, D: has room.
- User is in **Iran** → HuggingFace is throttled to ~6 KB/s, hf-mirror blocked, X/Twitter
  blocked, and international payment rails are effectively unavailable. This rules out
  "just pay for the API" and "just download the model" answers.
- User is a capable operator, not a JS/TS developer. Explain *why*, not just *what*.
  They will (correctly) push back when an agent drifts from root-causing into flailing.

---

## 2. Environment / how to run

```bash
cd D:/Mega/031-AI/worldmonitor-main
docker compose up -d                                  # normal start
docker compose up -d --no-deps worldmonitor           # env-only change to the app
docker compose up -d --build --no-deps worldmonitor   # app code/CSS change
docker compose up -d --build --no-deps ais-relay      # relay code change
```

- Dashboard: **http://localhost:3000** — hard-refresh (Ctrl+Shift+R) after CSS/JS builds;
  asset filenames are hashed and browsers cache aggressively.
- **Never** rebuild the relay unnecessarily — every restart re-resolves 56 Telegram
  usernames and can trigger a multi-hour `FLOOD_WAIT`. Use `--no-deps <service>`.
- Docker Desktop is often *not running* at session start. Start it and wait for
  `docker info` to succeed (~30–180 s).
- LM Studio must be running with a model loaded for any AI feature:
  `~/.cache/lm-studio/bin/lms.exe ls | ps | load <model> --gpu max --context-length 16384 --yes`
  Server is on **port 1761** (not the 1234 default). Models live in `D:\AI\LLM\<publisher>\<repo>\*.gguf`.

**Services** (docker-compose.yml): `worldmonitor` (app+nginx+sidecar API) · `ais-relay`
(data poller incl. Telegram, :3004) · `redis` · `redis-rest`.

---

## 3. Code map — the ~12 files that matter, and how they connect

Upstream is huge; this is the entire surface we touch. Follow the arrows rather than
opening files at random.

### 3a. Telegram ingestion chain
```
data/telegram-channels.json          56 curated OSINT channels (handle/label/topic)
        ↓ read by
scripts/ais-relay.cjs                GramJS poller + HTTP server on :3004
  · TELEGRAM_* env, polls every 60s, serves GET /telegram/feed
  · in-memory telegramState.items (cap 200), newest-first
  · ~line 1067 TELEGRAM_STARTUP_DELAY_MS; ~9812 the /telegram route
        ↓ HTTP (x-relay-key auth)
api/telegram-feed.js                 edge handler, proxies relay → app
        ↓
src/services/telegram-intel.ts       client fetchers + types
        ↓
src/components/TelegramIntelPanel.ts THE panel (see 3c)
```

### 3b. AI summarization chain
```
src/components/TelegramIntelPanel.ts   SUMMARIZE btn / auto-timer / فا toggle
        ↓ fetchTelegramSummary() in src/services/telegram-intel.ts
api/telegram-summarize.js              ← WE WROTE THIS. Pulls relay feed, prompts LLM.
        ↓ OLLAMA_API_URL (host.docker.internal:1761)
LM Studio (host)                        qwen/qwen3.5-9b @ 16k ctx
```
Parallel CLI path (independent, still works):
`scripts/telegram/summarize.mjs` — map-reduce brief generator, writes
`scripts/telegram/summaries/*.md|json`. Run from `scripts/`.

### 3c. The panel (our most-edited file)
`src/components/TelegramIntelPanel.ts` (~664 lines) owns:
- **batch-arrival read state** — `seenIds` (localStorage `telegram-intel:seen-v2`) +
  `newIds`; `diffBatch()` marks whatever's new in a refresh
- **scroll anchoring** in `renderItems()` — capture scrollTop/scrollHeight, restore
  offset by the growth so prepended messages don't shove your reading position
- **brief drawer** — persistent, history of 8, slide animation
- **toolbar** — SUMMARIZE, auto-interval select, countdown, فا (Persian) toggle, N NEW pill

### 3d. Other integration points
```
src/services/mission-presets.ts   MISSION_PRESETS[] + MissionPresetId union
                                  ← we added the 'recon-desk' preset (27 panels/16 layers)
src/config/panels.ts              ALL_PANELS (105) — panel id catalog
src/config/map-layer-definitions.ts  valid map layer keys
src/components/RadialMissionMenu.ts  ← WE WROTE THIS. Arc menu overlay.
        ↓ dispatches CustomEvent 'wm:apply-mission'
src/app/event-handlers.ts         listener added next to the resize handler →
                                  private applyMissionPreset()
src/App.ts                        mounts the radial menu after eventHandlers.init()
src/styles/main.css               (27k lines) our HUD theme is APPENDED AT THE END
docker/nginx.conf                 THE REAL nginx config (NOT nginx.conf.template)
src-tauri/sidecar/local-api-server.mjs  the app's API server in docker mode too;
                                  owns the SSRF allowlist
```

---

## 4. Hard-won gotchas — do not rediscover these

**① MTProto over port 80 is silently swallowed on this machine. (THE big one.)**
GramJS defaults to `149.154.167.91:80`. From inside Docker the TCP handshake completes,
the client sends its LAYER packet, and **no reply ever comes** — no RST, no error, just a
hang → `Telegram poll stuck for 240s` forever. The *host* works fine on :80, which is why
the session always looks healthy and why regenerating it seems to "fix" things briefly.
**Fix (applied):** `scripts/ais-relay.cjs` passes `useWSS: true` → port 443. Override with
`TELEGRAM_USE_WSS=false`.
*Debug technique:* run the identical probe on host vs inside the container
(`docker cp` + `MSYS_NO_PATHCONV=1 docker exec … node /tmp/probe.mjs`). `nc -z` is
**misleading** — it only tests the handshake, never payload delivery.

**② qwen3.5-9b always reasons; you cannot turn it off.**
`/no_think` (system *and* user), `"think":false`, `chat_template_kwargs.enable_thinking:false`,
`reasoning_effort` — **all fail**. It burns hidden tokens *before* any visible content, and
that cost **scales with input**: 3 msgs → ~1,489 tokens; 15 msgs → ~6,326; Persian output →
~8,123. Any caller with a small `max_tokens` gets an **empty or truncated** response.
Working config: 16k context, `LMSTUDIO_MAP_TOKENS=12000`, ~12k-char chunks.
Free-form prose needs *more* headroom than schema-constrained JSON (a JSON schema forces it
to stop thinking; free text doesn't).
⚠️ This breaks worldmonitor's built-in LLM features, which assume a non-reasoning model:
`summarize-article.ts` maxTokens **100**, `classify-event.ts` **50**, `llm.ts` defaults 600/1500.

**③ nginx cut long AI requests at exactly 120 s.**
`docker/nginx.conf` (**not** `nginx.conf.template`, which is a stale different file) had
`proxy_read_timeout 120s` → HTTP 504 mid-generation. Fixed with a dedicated
`location /api/telegram-summarize` block at 900 s (nginx longest-prefix wins).
The entrypoint renders the template to **`/tmp/nginx.conf`** via envsubst — the
`/etc/nginx/nginx.conf` inside the image is a stale leftover; don't inspect it.

**④ The app's SSRF guard blocks its own internal services.**
`src-tauri/sidecar/local-api-server.mjs` allowlists only `UPSTASH_REDIS_REST_URL` at
startup. We added `WS_RELAY_URL` **and** the LLM origin (`OLLAMA_API_URL`/`LLM_API_URL`)
in the docker-mode block. Without it: `SSRF blocked: Hostname resolves to a private/reserved
IP address`.

**⑤ Env vars must be wired in BOTH `.env` and `docker-compose.yml`.**
Twice we chased "the setting isn't working" when compose simply wasn't passing it
(`LMSTUDIO_MAP_TOKENS` silently fell back to its 5000 default). Always verify:
`docker exec worldmonitor sh -c 'echo $VAR'`.

**⑥ npm lockfile version skew breaks the Docker build.**
Host npm 11 writes lockfiles that the build image's npm 10.9.8 (node:22-alpine) rejects
(`Missing: utf-8-validate@5.0.10`). Host `npm install` does **not** fix it. Regenerate with
the *same* npm:
`docker run --rm -v "$(pwd -W):/app" -w /app node:22-alpine sh -c 'cd /app && npm install --package-lock-only --ignore-scripts'`
(needs `MSYS_NO_PATHCONV=1` from Git Bash). Three lockfiles: root, `scripts/`, `docker/runtime-`.
*As of 2.10.0 upstream ships clean lockfiles — only re-do this if `npm ci` fails again.*

**⑦ A 502 from `/api/telegram-summarize` is usually OUR handler's own JSON error**
(it returns 502 on empty/failed LLM), not nginx. **Always capture the body**
(`BODY=$(curl -s …)`) before theorising. `curl -o /tmp/x` can silently fail under Git Bash.

**⑧ Relay restarts are expensive.** Each one re-resolves 56 usernames; too many in a row
→ `FLOOD_WAIT` of ~3.6 h on `contacts.ResolveUsername` (channels drop to ~31/56 until it clears).

**⑨ CSS:** `main.css` is 27k lines. Our theme is **appended at the end** (later rules win at
equal specificity). Before styling, `grep` for existing rules — the unread-vs-LIVE bug was a
pre-existing `.is-live { border-left-color: var(--green) }` colliding with our unread rail.

---

## 5. ⚠️ Re-apply after any worldmonitor GitHub update

`.env` is git-ignored and survives. These touch **tracked** files and will be wiped:

1. `docker-compose.yml` — ais-relay `TELEGRAM_*` + `RELAY_SHARED_SECRET` + `TELEGRAM_STARTUP_DELAY_MS`; app `RELAY_SHARED_SECRET` + `OLLAMA_*` + `LMSTUDIO_MAP_TOKENS` + `LLM_TIMEOUT_MS`
2. `src-tauri/sidecar/local-api-server.mjs` — SSRF allowlist for `WS_RELAY_URL` and the LLM origin
3. `scripts/ais-relay.cjs` — **`useWSS: true`** (gotcha ①)
4. `docker/nginx.conf` — the 900 s `location /api/telegram-summarize` block
5. `scripts/telegram/summarize.mjs` — env-configurable token budgets
6. New files (safe, but confirm they survived): `api/telegram-summarize.js`, `src/components/RadialMissionMenu.ts`
7. `src/components/TelegramIntelPanel.ts`, `src/services/telegram-intel.ts`, `src/services/mission-presets.ts`, `src/app/event-handlers.ts`, `src/App.ts`, `src/styles/main.css`

---

## 6. What is built and working

- **Telegram ingestion** — 56 channels, ~200 msgs live, multi-language (EN/FA/AR/RU/UK/HE).
- **AI brief** — `/api/telegram-summarize` produces a real analyst brief (Brief + Key Points
  with `[Channel]` attribution). Verified end-to-end. ~166 s for 15 messages.
- **Persian mode** (`فا` toggle) — full brief in Persian, single pass, proper nouns kept Latin.
- **Brief drawer** — persistent, slide animation, last 8 briefs with ‹ › history.
- **Read/unread** — batch-arrival based, `NEW` chips + glow dot + arrival pulse +
  `N NEW SINCE hh:mm` divider + acknowledge pill.
- **Scroll anchoring** — new messages stack above without moving what you're reading.
- **Recon Desk mission preset** — 27 OSINT panels (collection → AI fusion → threat →
  verification → context) + 16 map layers.
- **Radial mission menu** — arc overlay, left edge, applies presets.
- **HUD theme** — black/mint, inverted fills, corner ticks; global via design tokens with
  semantic threat colors deliberately preserved; light theme untouched.

---

## 7. Current state / immediate next actions

- Stack runs; Telegram healthy over :443. Some channels may still be in `FLOOD_WAIT`.
- **LM Studio may not be running** — required for SUMMARIZE.
- **Pending (blocked on user):** a small **non-reasoning** model. The 1.5B download failed
  (HF throttled ~6 KB/s from Iran; `lms get` "fetch failed"; hf-mirror blocked). User must
  download in-browser to
  `D:\AI\LLM\Qwen\Qwen2.5-1.5B-Instruct-GGUF\qwen2.5-1.5b-instruct-q4_k_m.gguf`
  (note the **-GGUF** repo suffix; `.safetensors` is **not** loadable by LM Studio).
  Suggested better fit: **Qwen2.5-7B-Instruct Q4_K_M (~4.7 GB)**.
  When it lands: set `OLLAMA_MODEL`, load it, drop `LMSTUDIO_MAP_TOKENS` 12000 → ~1500,
  and optionally point `LLM_TOOL_PROVIDER=ollama` + `LLM_TOOL_MODEL` at it to revive
  worldmonitor's built-in AI panels (gotcha ②).
- **Next roadmap phase: Phase 3 — geolocate AI-extracted events onto the map.**
  JSON-schema extraction already proven (correctly pulled `place_names: ["Khuzestan Province"]`
  and resolved "two days" → a date). Reuse worldmonitor's existing geo/entity services.
- **Open consult (X/Twitter):** no viable paid route from Iran. Recommendation was
  (1) tag X-origin content already arriving via Telegram reposts, (2) add Bluesky Jetstream
  (free/open), (3) only then consider burner-account scraping. Not started.

---

## 8. Working agreements with this operator

- Root-cause before patching; they will call out flailing (rightly).
- Verify claims by running the thing, not by inspecting config paths.
- Report failures plainly with the actual output.
- Prefer `.env` (survives updates) over code constants for anything tunable.
- Explain trade-offs; they make the call.
