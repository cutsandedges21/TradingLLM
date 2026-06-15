# Hosting Trading LLM (use it on your phone without your desktop)

The app is a **stateful server** — it keeps a process running, writes your paper
account/journal to disk, streams responses, and makes multi-second data calls. So it
needs a host that runs a **persistent container/VM**, *not* serverless (that's why
Vercel only ever returned 404). The container is built by the `Dockerfile`: it compiles
the React UI and serves it together with the API on port 8000.

Your **API keys are never baked into the image** — they're passed as environment
variables. Your **private data persists** only if you mount a volume at `/app/memory`.

---

## Pick a host

| Host | Cost | Always-on? | Keeps your data? | Effort |
|---|---|---|---|---|
| **Fly.io** (recommended) | ~free–$3/mo | ✅ (`min_machines_running=1`) | ✅ with a volume | Low — one CLI |
| **VPS** (Hetzner ~$5, DigitalOcean, or **Oracle Cloud "Always Free"** ARM VM = $0) | $0–6/mo | ✅ | ✅ (real disk) | Medium — SSH + Docker |
| **Render** | free / $7 | free tier **sleeps** ~15 min | ❌ free (ephemeral) / ✅ paid disk | Low — connect GitHub |
| **Raspberry Pi / old laptop at home + Tailscale** | $0 (own HW) | ✅ if left on | ✅ | Low–Medium |

**Recommendation:** **Fly.io** for the least hassle with persistence; an **Oracle Cloud
Always-Free VM** if you want $0 forever and don't mind a bit more setup. Both run the same
`Dockerfile`.

---

## Option A — Render: deploy straight from GitHub (no CLI) ⭐ easiest

This is the "like Vercel, but it runs a real server" path — connect the repo once and it
**redeploys on every push to `main`**. The repo already includes a `render.yaml` blueprint.

1. Go to **https://render.com** → sign up with GitHub.
2. **New ▸ Blueprint** → pick the **`TradingLLM`** repo. Render reads `render.yaml`,
   sees the `Dockerfile`, and proposes a web service + a 1 GB disk at `/app/memory`.
3. It will prompt for the secret env vars (they're marked `sync: false`):
   - `TRADING_LLM_API_KEY` = a long random string (this is your phone's access key)
   - `GEMINI_API_KEYS`, `OPENROUTER_API_KEYS`, `FINNHUB_API_KEY` = your keys
   - *(optional)* `ALPACA_PAPER_KEY`, `ALPACA_PAPER_SECRET`
4. **Apply** → first build takes a few minutes. You get a URL like
   `https://trading-llm.onrender.com`.
5. **On your phone:** open that URL → **Settings ▸ Remote access** → paste
   `TRADING_LLM_API_KEY` → *Save & reconnect*. Done — desktop off, works anywhere. 🎉

**Cost:** the blueprint uses the **Starter** plan (~$7/mo) because a persistent disk +
always-on require a paid plan. For **$0**, edit `render.yaml`: set `plan: free` and remove
the `disk:` block — but the free instance **sleeps after ~15 min** (≈50 s cold start) and
**loses your paper data** when it recycles. Good for trying it; not for daily use.

> No-CLI alternatives that also deploy from GitHub: **Railway** (great DX, persistent
> volumes, ~$5/mo, no real free tier) and **Koyeb** (has a small free instance). Both read
> the same `Dockerfile`. **Fly.io can auto-deploy from GitHub too**, but via a GitHub Action
> with a `FLY_API_TOKEN` secret — the CLI path below is simpler to start.

---

## Option B — Fly.io (recommended if you want cheapest always-on)

1. **Install the CLI** and sign in (a card is required even on the free allowance):
   ```bash
   # Windows (PowerShell):  iwr https://fly.io/install.ps1 -useb | iex
   fly auth login
   ```
2. **Adopt the config** (edit `app` to a unique name + `primary_region` in `fly.toml` first):
   ```bash
   fly launch --no-deploy --copy-config
   fly volumes create tllm_data --size 1        # 1 GB persistent disk for /app/memory
   ```
3. **Set your secrets** (these override `config/api_keys.json`, which isn't shipped):
   ```bash
   fly secrets set \
     TRADING_LLM_API_KEY="pick-a-long-random-string" \
     GEMINI_API_KEYS="your_gemini_key" \
     OPENROUTER_API_KEYS="your_openrouter_key" \
     FINNHUB_API_KEY="your_finnhub_key"
   # optional real paper broker:
   # fly secrets set ALPACA_PAPER_KEY="..." ALPACA_PAPER_SECRET="..."
   ```
4. **Deploy:**
   ```bash
   fly deploy
   ```
   You'll get a URL like `https://trading-llm.fly.dev`.
5. **On your phone:** open that URL → **Settings → Remote access** → paste the same
   `TRADING_LLM_API_KEY` → *Save & reconnect*. Works from anywhere, desktop off. 🎉

---

## Option C — A VPS (Oracle Always-Free or any $5 droplet)

On the server (with Docker installed):
```bash
git clone https://github.com/cutsandedges21/TradingLLM.git && cd TradingLLM
docker build -t trading-llm .
docker run -d --restart unless-stopped -p 80:8000 \
  -v tllm_data:/app/memory \
  -e TRADING_LLM_API_KEY="pick-a-long-random-string" \
  -e GEMINI_API_KEYS="..." -e OPENROUTER_API_KEYS="..." -e FINNHUB_API_KEY="..." \
  --name trading-llm trading-llm
```
Open the firewall for the port, point a domain at it (optional), and ideally put it behind
HTTPS (Caddy/Cloudflare). Then open it on your phone and enter the key in Settings.

---

## Required / optional environment variables

| Var | Purpose |
|---|---|
| `TRADING_LLM_API_KEY` | **Required for remote access** — the key your phone sends. Pick something long/random. |
| `GEMINI_API_KEYS` | Gemini (primary brain). Comma-separated for rotation. |
| `OPENROUTER_API_KEYS` | OpenRouter fallback. |
| `FINNHUB_API_KEY` | Real-time quotes + news. |
| `ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET` | Optional real paper brokerage. |
| `TRADING_LLM_HOST` / `TRADING_LLM_PORT` | Bind host/port (image defaults: `0.0.0.0` / `8000`). |

---

## Notes & honest caveats

- **Persistence:** only `/app/memory` persists (via the volume) — your paper account,
  journal, alert rules, signal cache. Settings changed in the UI (e.g. watchlist) live in
  the image's `config/settings.json` and **reset on redeploy**; set the watchlist before
  building, or commit it. The access key lives in the env var, so it persists fine.
- **Security:** anyone with the URL **and** the key can drive your (paper) account and use
  your LLM quota — keep both private and use a strong key. Trading is **simulated** by
  default; Alpaca is opt-in paper only.
- **Cost reality:** truly-free + always-on + persistent points to Oracle's Always-Free VM
  (or a home device + Tailscale). Fly is the easiest and only a few dollars at most.
- This file is the same app you run locally; nothing about the trading logic changes.
