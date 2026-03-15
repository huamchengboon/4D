# ── Stage 1: Build frontend ─────────────────────────────────────
FROM oven/bun:1.2-alpine AS frontend
WORKDIR /app/web-frontend

COPY web-frontend/package.json web-frontend/bun.lock* ./
RUN bun install --frozen-lockfile 2>/dev/null || bun install

COPY web-frontend/ ./
RUN bun run build

# ── Stage 2: Backend + serve frontend ───────────────────────────
FROM python:3.13-slim AS app
WORKDIR /app

# Install Python deps (no Rust extension; scraper falls back to Python)
COPY requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copy backend and analysis code
COPY pyproject.toml ./
COPY analysis/ ./analysis/
COPY web/ ./web/
COPY scrape_history.py scraper.py ./

# Copy built React frontend (must have index.html for SPA to be served at /)
COPY --from=frontend /app/web-frontend/dist ./frontend_dist
RUN test -f /app/frontend_dist/index.html || (echo "React build missing index.html" && exit 1)

# Data dir for volume mount (CSV + SQLite)
RUN mkdir -p /data

ENV FRONTEND_DIST=/app/frontend_dist
ENV 4D_HISTORY_CSV=/data/4d_history.csv
ENV API_CACHE_DB=/data/api_cache.sqlite3

EXPOSE 8000
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
