# SPIDERNET — Project Roadmap

*(Kept in `D:\Mega\031-AI\` — the parent of both projects — so a worldmonitor GitHub update can't wipe it.)*

## Mission
A human-in-the-loop OSINT situational-awareness dashboard. Ingest **Telegram channels + multi-language news**, use a **local LLM (LM Studio, OpenAI-compatible)** to translate / classify / extract / **summarize** and geolocate events, and mark them on the map. The AI proposes; the operator judges.

## Base decision (locked 2026-07-11)
- **Base project = `D:\Mega\031-AI\worldmonitor-main`** (more advanced + optimized). Vite/React + Node + Convex; multi-service Docker (worldmonitor app + ais-relay + redis + redis-rest).
- **ShadowBroker = parts donor** (`D:\Mega\031-AI\Shadowbroker`). We transfer only features the user selects (list TBD).
- Telegram in worldmonitor uses **GramJS** (npm `telegram`), not Python Telethon. Sessions are library-specific → regenerate here.

---

## Phase 0 — Stand up worldmonitor  ✅ (mostly done)
- [x] Fix Docker build: npm lockfile npm-version skew (regenerate all 3 lockfiles with node:22-alpine npm 10, not host npm 11) + transient Alpine DNS (retry / pin Docker DNS).
- [x] worldmonitor stack builds and runs.

## Phase 1 — Activate Telegram  ✅ DONE 2026-07-11 (verified: 56/56 channels, 200 msgs flowing to the panel)
- [x] Wire `TELEGRAM_API_ID/HASH/SESSION/CHANNEL_SET` into the `ais-relay` service in `docker-compose.yml`.
- [x] Seed `.env` with API ID/hash + `TELEGRAM_CHANNEL_SET=full`.
- [x] User generated the GramJS session (`node scripts/telegram/session-auth.mjs`) → `.env`.
- [x] **2.10.0 fix #1:** relay FATALs without `RELAY_SHARED_SECRET` → generated one, wired into BOTH the app and relay services.
- [x] **2.10.0 fix #2:** app-side SSRF guard blocked the app→relay fetch (only Redis was allowlisted). Patched `src-tauri/sidecar/local-api-server.mjs` to allowlist `WS_RELAY_URL`'s origin in docker mode.
- [x] Verified: relay polls all 56 channels; `/api/telegram-feed` returns live items; panel populates.

> ⚠️ **Re-apply after any GitHub update** (these touch tracked files): (1) `ais-relay` TELEGRAM_* + `RELAY_SHARED_SECRET` wiring in `docker-compose.yml`; (2) app `RELAY_SHARED_SECRET` wiring; (3) the `WS_RELAY_URL` SSRF-allowlist block in `local-api-server.mjs`. `.env` survives (git-ignored). All three are in memory.

## Phase 2 — Local AI over Telegram  ✅ CORE DONE 2026-07-28
- [x] **LM Studio fixed** — models were in `D:\LLM` but `settings.json` pointed `downloadsFolder` at `D:\AI\LLM` (empty). Moved the folder (same drive = instant). Model loads + verified on real Farsi OSINT text (translation, classification, and correct relative-time resolution "two days"→date).
- [x] **`scripts/telegram/summarize.mjs` WORKING** — produces a real briefing (Exec Summary / Key Developments with [Channel] attribution / Early Signals) → `.md` + `.json`. Budgets made env-configurable; see `.env` keys `LMSTUDIO_*`.
- [x] Documented the reasoning-model constraint (below).
- [ ] Optional: schedule it (e.g. a morning run) and/or surface the brief in the UI.

### ⚠️ Reasoning-model constraint (important, learned the hard way)
qwen3.5-9b **always** reasons — `/no_think`, `think:false`, `chat_template_kwargs.enable_thinking:false`, and `reasoning_effort` ALL fail to disable it. It spends ~1,100–1,500 hidden tokens *before* any visible output, so **any caller with a small `max_tokens` gets an EMPTY response**.
- Free-form summarization needs MORE headroom than schema-constrained extraction (a JSON schema forces it to stop thinking; free text does not).
- Working budgets: 16k context, 5,000 completion, ~12,000-char chunks. ~3 min per call.
- **This breaks worldmonitor's in-app LLM features**, whose call sites assume a non-reasoning model: `summarize-article.ts` maxTokens **100**, `classify-event.ts` **50**, `llm.ts` defaults 600/1500. Those return empty and, with no fallback provider, produce nothing.
- **Fix when wanted:** download a small NON-reasoning instruct model (Qwen2.5-7B-Instruct / Llama-3.1-8B-Instruct, ~5 GB Q4) and point `LLM_TOOL_PROVIDER=ollama` + `LLM_TOOL_MODEL=<that model>` at it, keeping qwen3.5-9b for `LLM_REASONING_*`. The two profiles are separately configurable by design.

## TODO — deferred (user will do later)
- [ ] **Download a small NON-reasoning instruct model** (Qwen2.5-7B-Instruct or Llama-3.1-8B-Instruct, ~5 GB Q4) and wire `LLM_TOOL_PROVIDER=ollama` + `LLM_TOOL_MODEL=<it>`, keeping qwen3.5-9b on `LLM_REASONING_*`. Unlocks: worldmonitor's in-app AI (news summarization / event classification, currently dead — their call sites budget 50–100 tokens) and ~10× faster per-event extraction (~2–5 s vs ~47 s) which makes Phase 3 batch processing practical. *User decision 2026-07-28: stay on qwen3.5-9b for now, download later.*

## Phase 3 — Geolocate & map
- [ ] Ensure extracted/summarized Telegram events get geolocated and placed on worldmonitor's map layer (worldmonitor already has geo/entity-extraction services — reuse over rebuild).

## Phase 4 — Transfer chosen features from ShadowBroker
- [ ] **User provides the list.** Candidate donors (ShadowBroker strengths): visual modes (FLIR/NVG/CRT), specific feed fetchers, the AI-pin overlay system, region dossier, SAR change detection. Port each into worldmonitor's architecture, not wholesale.

## Phase 5 — Update worldmonitor to latest GitHub
- [ ] AFTER Telegram is verified: pull the latest worldmonitor from GitHub.
- [ ] ⚠️ A re-clone/overwrite will likely reset `docker-compose.yml` → **re-apply the ais-relay Telegram env wiring** (`.env` is git-ignored so it survives). Re-run the lockfile-with-npm-10 fix if `npm ci` breaks again.

---

### Superseded
`D:\Mega\031-AI\Shadowbroker\TODO.md` was the ShadowBroker-based roadmap (Phase 1 Telethon ingestion was built + connected as RedMist2077, now sidelined). Kept for reference / as the donor feature inventory.
