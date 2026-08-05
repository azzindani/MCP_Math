# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────────
# math-mcp-server — production container.
#
# Two-stage build: uv sync into a venv, then copy venv + src into a slim
# python:3.12 runtime. No compiled artifact — src/ runs directly via uv/python.
#
# Build:            docker build -t math-mcp-server:latest .
# Run stdio (n/a):  stdio is for local process-spawning clients, not containers.
# Run HTTP:         docker run --rm -p 8765:8765 math-mcp-server:latest
# Run with auth:    docker run --rm -p 8765:8765 -e MATH_API_KEY=secret math-mcp-server:latest
# ─────────────────────────────────────────────────────────────────────────────

ARG PYTHON_VERSION=3.12-slim

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION} AS runtime

RUN groupadd -r math && useradd -r -g math math \
    && mkdir -p /home/math && chown math:math /home/math

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY pyproject.toml ./

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    MATH_TRANSPORT=http \
    MATH_HOST=0.0.0.0 \
    MATH_PORT=8765

USER math
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"MATH_PORT\"]}/health', timeout=3)" || exit 1

ENTRYPOINT ["python", "/app/src/server.py"]
