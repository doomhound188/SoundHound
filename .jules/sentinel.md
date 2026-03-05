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

## 2026-12-05 - SSRF Obfuscation Bypass via Hex/Octal/Integer IPs
**Vulnerability:** The SSRF check was vulnerable to evasion because it only checked the literal URL hostname against a string-based blacklist. Attackers could obfuscate local or restricted IPs using Hex (0x7f000001), Octal (0177.0.0.1), or Integer (2852039166) formats to reach restricted targets like `127.0.0.1` and `169.254.169.254`.
**Learning:** String-matching against hostnames is insufficient to block SSRF. The application must perform asynchronous DNS resolution (e.g., using `asyncio.get_running_loop().getaddrinfo`) and evaluate the underlying IP address using libraries like `ipaddress` for strict range-based validation (e.g. `is_loopback`, `is_private`).
**Prevention:** Updated `validate_query` to an `async` function and implemented an IP validation step post-resolution, properly blocking obfuscated IPs. Implemented tests to catch hex, octal, and integer variants. Synchronous calls like `socket.gethostbyname()` and global state changes like `socket.setdefaulttimeout()` must be strictly avoided to prevent blocking the async loop.
