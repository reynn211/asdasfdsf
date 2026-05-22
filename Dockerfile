# Combined single-service Dockerfile for Render (free tier) / any Docker PaaS.
# Builds C++ analyzer + frontend, serves everything from one FastAPI process.
# syntax=docker/dockerfile:1.6

# ---------- Stage 1: Build C++ analyzer ----------
FROM debian:bookworm-slim AS cpp-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential cmake ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY backend/CMakeLists.txt ./
COPY backend/include/ ./include/
COPY backend/src/ ./src/
COPY backend/tests/ ./tests/

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release -j$(nproc)

# ---------- Stage 2: Build frontend ----------
FROM node:20-alpine AS frontend-builder

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ .
ENV VITE_API_BASE=""
RUN npm run build

# ---------- Stage 3: Python runtime (serves API + static frontend) ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# Python sources + data
COPY backend/main.py backend/database.py backend/stop_words.py ./
COPY backend/data/ ./data/

# C++ analyzer binary
COPY --from=cpp-builder /src/analyzer ./analyzer
RUN chmod +x ./analyzer

# Frontend build output → /app/static
COPY --from=frontend-builder /app/dist ./static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/history || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
