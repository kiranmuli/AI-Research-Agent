# syntax=docker/dockerfile:1

# --- build stage: install dependencies into a venv ---
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /app
COPY pyproject.toml README.md ./
# Copy the packages so the project is installable (pulls in all dependencies).
COPY app ./app
COPY research_agent ./research_agent
RUN pip install --upgrade pip && pip install .

# --- runtime stage: slim image, non-root user ---
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=5000

# curl is used by the compose healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY . .
RUN chmod +x deploy/entrypoint.sh && chown -R appuser:appuser /app

USER appuser
EXPOSE 5000

ENTRYPOINT ["deploy/entrypoint.sh"]
CMD ["web"]
