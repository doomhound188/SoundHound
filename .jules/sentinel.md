## 2024-05-26 - Authorization Bypass in Voice Commands
**Vulnerability:** Missing Authorization (IDOR/Griefing)
**Learning:** Destructive commands (`stop`, `skip`, `leave`, `clear`) did not verify if the user was in the same voice channel as the bot. This allowed any user (even those not listening) to disrupt playback for everyone else.
**Prevention:** Implemented an `is_privileged` check to ensure the command invoker shares the same voice channel as the bot before allowing playback modifications.

## 2026-01-22 - Local File Inclusion in Search Queries
**Vulnerability:** Input handling for the `play` command allowed dangerous protocols like `file://` in search queries.
**Learning:** Downstream libraries (like Lavalink or Wavelink) might process file URIs if not explicitly blocked, potentially exposing local server files.
**Prevention:** Sanitized user input in `bot_logic.validate_query` to strictly block `file://` protocol before processing.

## 2026-10-18 - HTTPS Downgrade in Lavalink Connection
**Vulnerability:** The bot explicitly stripped `https://` from the `LAVALINK_URI` and hardcoded `http://`, forcing insecure connections even when SSL was configured.
**Learning:** Hardcoded URI reconstruction can inadvertently disable security features. Always respect the provided scheme or use library defaults that handle parsing correctly.
**Prevention:** Updated `parse_lavalink_uri` to detect and preserve the URI scheme (http/https).

## 2026-10-23 - SSRF via Unrestricted URL Access in Search Queries
**Vulnerability:** Input validation in `validate_query` did not block dangerous hostnames like `169.254.169.254` (cloud metadata service) or `localhost`.
**Learning:** Checking for protocol prefixes (like `file://`) is insufficient. Attackers can use standard protocols (`http/s`) to target internal services if hostnames are not validated.
**Prevention:** Implemented a blocklist of dangerous hostnames (localhost, loopback, metadata IPs) using `urllib.parse.urlparse` to sanitize search queries.
