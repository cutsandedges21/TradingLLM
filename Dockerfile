# Trading LLM — single container that builds the React UI and serves it + the API.
# Deploy to any container host (Fly.io, Render, Railway, a VPS). Keys come from
# env vars (never baked in); runtime data lives in /app/memory (mount a volume).

# --- stage 1: build the web UI ---
FROM node:20-slim AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build            # -> /web/dist (served by FastAPI)

# --- stage 2: python runtime ---
FROM python:3.12-slim
# Note: no fixed TRADING_LLM_PORT — the app honors a host-injected $PORT
# (Render/Railway), and falls back to 8000 (used by Fly's internal_port).
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRADING_LLM_HOST=0.0.0.0 \
    TRADING_LLM_NO_BROWSER=1
WORKDIR /app

# Build tools only while installing wheels that may need compiling, then removed.
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install -r requirements.txt && apt-get purge -y gcc g++ && apt-get autoremove -y

# App code + config defaults + the built UI from stage 1.
COPY trading_llm/ ./trading_llm/
COPY app_web.py LEARN_TO_TRADE.md ./
COPY config/ ./config/
COPY --from=web /web/dist ./web/dist

# Private trading data persists here — mount a volume at /app/memory.
RUN mkdir -p /app/memory
VOLUME ["/app/memory"]

EXPOSE 8000
CMD ["python", "app_web.py"]
