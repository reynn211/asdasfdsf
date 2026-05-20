# syntax=docker/dockerfile:1.6

# ---------- Stage 1: build the C++ analyzer with CMake ----------
FROM debian:bookworm-slim AS cpp-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Only copy what the C++ build needs so Python-side changes don't bust this layer.
COPY CMakeLists.txt ./
COPY include/ ./include/
COPY src/ ./src/
COPY tests/ ./tests/

RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release -j

# CMakeLists.txt sets RUNTIME_OUTPUT_DIRECTORY to the source root, so the
# built binary lands at /src/analyzer.

# ---------- Stage 2: Python runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Minimal runtime libs — libstdc++ for the analyzer binary, curl for healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libstdc++6 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Python sources + bundled stop-word data.
COPY main.py database.py stop_words.py ./
COPY data/ ./data/

# Compiled C++ analyzer from the builder stage. main.py expects it at
# backend/analyzer next to main.py.
COPY --from=cpp-builder /src/analyzer ./analyzer
RUN chmod +x ./analyzer

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/history || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
