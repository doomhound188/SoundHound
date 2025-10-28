FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system deps: ffmpeg for voice, and build/runtime deps for libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    build-essential \
    libffi-dev \
    libnacl-dev \
    git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage layer caching
COPY requirements.txt .

# Optional: pin pip/setuptools/wheel for smoother builds
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

# Copy the rest of the code
COPY . .

# Create non-root user
RUN useradd -m -u 10001 botuser \
 && chown -R botuser:botuser /app
USER botuser

# Default envs (can be overridden at runtime)
# ENV DISCORD_TOKEN= \
#     SPOTIFY_CLIENT_ID= \
#     SPOTIFY_CLIENT_SECRET=

# Healthcheck: simple python import/exit to ensure container is alive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, shutil; assert shutil.which('ffmpeg'), 'ffmpeg missing'; print('ok')" || exit 1

# Run the bot
CMD ["python", "bot.py"]
