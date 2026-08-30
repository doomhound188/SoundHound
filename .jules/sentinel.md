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

## 2026-11-23 - Server-Side Request Forgery (SSRF) in Search Queries
**Vulnerability:** The `validate_query` function checked for `file://` protocol but allowed HTTP/HTTPS requests to any host, including `localhost`, `127.0.0.1`, and cloud metadata services.
**Learning:** Checking protocol prefixes is insufficient. Validating the hostname is critical when the application can be tricked into making requests to internal resources.
**Prevention:** Enhanced `validate_query` to parse URLs starting with `http://` or `https://` and block requests to a blacklist of dangerous hostnames (`localhost`, `127.0.0.1`, `::1`, `0.0.0.0`, `169.254.169.254`).

## 2024-05-27 - DNS Rebinding & SSRF Vulnerability in Search Query Resolution
**Vulnerability:** The `validate_query` function checked for disallowed hostnames (e.g. `localhost`, `127.0.0.1`) only by string matching the initial hostname. This left the application vulnerable to Server-Side Request Forgery (SSRF) where an attacker could provide an external hostname that resolves to an internal or private IP address.
**Learning:** Validating hostnames against a string blacklist is insufficient to prevent SSRF because DNS resolution can map benign-looking external hostnames to local or private IP addresses. We must resolve the hostname to its underlying IPs and validate those IPs against safe ranges before allowing the request.
**Prevention:** Modified `validate_query` to be asynchronous. Implemented asynchronous DNS resolution via `asyncio.get_running_loop().getaddrinfo()` on the extracted hostname. The resolved IPs are then verified using the `ipaddress` module to ensure none are loopback, private, link-local, or unspecified. The resolution is wrapped in an `asyncio.wait_for` block to prevent hanging. The `bot.py` command handler was updated to await this new asynchronous function.
