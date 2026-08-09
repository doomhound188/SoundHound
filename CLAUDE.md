# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SoundHound is a Discord music bot built with `py-cord` (Discord API) and `wavelink` (Lavalink client). It connects to a separate Lavalink audio-node server to search and stream tracks from YouTube, SoundCloud, and Spotify into Discord voice channels.

## Commands

Install dependencies:
```
pip install -r requirements.txt
```

Run the bot locally (requires `.env` populated from `example.env`, and a reachable Lavalink node):
```
python bot.py
```

Run the full test suite:
```
python -m unittest discover -v
```

Run a single test file:
```
python -m unittest test_bot.py -v
python -m unittest test_uri_parsing.py -v
python -m unittest test_config_integration.py -v
```

Run a single test case/method:
```
python -m unittest test_bot.TestValidateQuery.test_validate_query_blocks_localhost -v
```

Run the full stack (bot + Lavalink) via Docker:
```
docker compose up --build
```

There is no linter/formatter configured in this repo (no flake8/ruff/black config) — don't introduce one unprompted.

## Architecture

**Two-process system.** The bot (this repo, Python) never touches audio directly — it delegates all searching/streaming/decoding to a separate **Lavalink** server (a JVM process, run via the `ghcr.io/lavalink-devs/lavalink:4` image in `docker-compose.yml`, configured by `application.yml`). `bot.py` connects to Lavalink over the URI in `LAVALINK_URI`/`LAVALINK_PASSWORD` and issues search/play calls through `wavelink`. When developing locally without Docker, a Lavalink node must be reachable independently.

**`bot.py` vs `bot_logic.py` split.** `bot.py` holds Discord-facing code: slash command definitions (`/join`, `/leave`, `/stop`, `/play`, `/queue`, `/skip`, `/clear`), event handlers, and interaction responses. `bot_logic.py` holds everything that can be unit-tested without a real Discord/Lavalink connection: query validation, the search cache, and the auto-play-next-track handler. This split exists specifically so tests can exercise business logic without needing live `discord`/`wavelink` objects — preserve it when adding commands (put non-Discord logic in `bot_logic.py`).

**Security-hardened input handling (`bot_logic.validate_query`).** User search queries are validated before being passed to Wavelink: length-capped (1000 chars, checked *before* stripping to avoid DoS via huge whitespace payloads), `file://` is blocked (LFI), and `http(s)://` URLs are parsed and checked against a hostname blacklist (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`, `169.254.169.254`) to prevent SSRF against internal/metadata endpoints. Any new code path that forwards user-supplied strings to Wavelink/Lavalink must go through this same validation.

**Voice-channel privilege model.** Destructive/playback-altering commands (`stop`, `skip`, `leave`, `clear`) call `is_privileged(inter, player)`, which requires the invoking user to be in the *same* voice channel as the bot. This prevents griefing by users outside the channel. Any new command that mutates playback state should use this same check.

**Search caching + request coalescing (`bot_logic.search_with_cache`).** An LRU cache (`OrderedDict`, capped at `MAX_CACHE_SIZE=100`) avoids redundant Lavalink searches for repeated queries. Concurrent identical in-flight searches are coalesced via a `_pending_searches` dict of shared `asyncio.Task`s, keyed by the (already-validated) query string, so parallel `/play` calls for the same song only hit Lavalink once. Cleanup of `_pending_searches` uses `try/finally` (not bare `except Exception`) because `asyncio.CancelledError` inherits from `BaseException`.

**Queue bounding.** `MAX_QUEUE_SIZE` (500, in `bot_logic.py`) is enforced in `/play` both for single tracks and when adding an entire playlist, to prevent memory exhaustion from unbounded queues.

**Concurrency pattern in `/play`.** Voice-channel connection (`get_or_connect_player`) and the Lavalink search (`search_with_cache`) are kicked off as separate `asyncio.Task`s and awaited independently, so the two I/O-bound operations overlap instead of running sequentially.

**Error handling toward users.** Internal exceptions (voice connection errors, search errors) are logged server-side with `print()` but never leaked to Discord users — user-facing messages are generic and sanitized. Log lines built from user input strip `\n`/`\r` to prevent log injection.

**Testing strategy: mock heavy deps at `sys.modules` level.** `discord`, `wavelink`, and `dotenv` are C/network-dependent and not suitable for unit tests. Test files replace them in `sys.modules` with `MagicMock()` *before* importing `bot`/`bot_logic` (see the top of `test_bot.py` and `test_config_integration.py`). Follow this same pattern for new tests rather than trying to install/run real Discord or Lavalink connections.

## Configuration

Environment variables (see `example.env`, loaded via `.env` + `python-dotenv`):
- `DISCORD_TOKEN` — bot token (required to run).
- `LAVALINK_URI` — Lavalink node address, e.g. `http://lavalink:2333` (Docker service name) or `http://localhost:2333` locally. Parsed by `bot.parse_lavalink_uri`, which preserves `https://` if present rather than forcing `http://`.
- `LAVALINK_PASSWORD` — must match the value in `application.yml` used by the Lavalink container.
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` — passed through to Lavalink's Spotify source plugin config in `application.yml`.

## CI/CD

`.github/workflows/docker-publish.yml` builds a multi-arch (`linux/amd64,linux/arm64`) Docker image on every push/PR to `main` and on `v*.*.*` tags. It only *pushes* to `ghcr.io/<repo>` when the event is not a `pull_request` (PRs just build, to validate the Dockerfile). The Dockerfile installs `ffmpeg` (required for voice) and runs the bot as a non-root user (`botuser`).

## `.jules/` learning logs

`.jules/bolt.md` and `.jules/sentinel.md` are running logs of past optimization and security learnings for this codebase (e.g. why prefix checks use slicing instead of `.lower().startswith()`, why generator expressions are used in `str.join()`, the history behind the SSRF/LFI/privilege checks above). Skim them before making performance- or security-sensitive changes — they document *why* the current code looks the way it does, and regressions on these points have happened before.
