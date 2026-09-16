FROM oven/bun:1.2.14-slim AS base

ENV BUILDKIT_COLORS=0 \
    BUN_INSTALL=/usr/local/bin

# Install system deps: ffmpeg for voice
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy bun.lock and package.json first to leverage layer caching
COPY bun.lock package.json ./

RUN bun install --frozen-lockfile --production

# Copy the rest of the code
COPY . .

# Create non-root user
RUN useradd -m -u 10001 botuser \
 && chown -R botuser:botuser /app
USER botuser

# Healthcheck: simple bun script to check if ffmpeg exists
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD bun -e "const { $ } = require('bun'); await $\`which ffmpeg\`.quiet().catch(() => process.exit(1)); process.exit(0)"

# Run the bot
CMD ["bun", "run", "src/index.ts"]
