# Sentinel's Journal

## 2024-05-23 - Input Validation and Information Leakage
**Vulnerability:** Input Validation (DoS) and Information Leakage
**Learning:** The `play` command accepted queries of arbitrary length, which could potentially lead to DoS. Additionally, exception messages were being sent directly to the user, potentially leaking internal details.
**Prevention:** Implemented input length validation (max 1000 characters) for search queries. Also sanitized error messages sent to the user while logging full errors to the console.

## 2024-05-24 - Rate Limiting and Log Injection
**Vulnerability:** Missing Rate Limiting and Log Injection
**Learning:** The `play` command lacked rate limiting, making it susceptible to spam/DoS attacks on the external Lavalink/YouTube service. Additionally, user input was logged directly without sanitization, allowing for Log Injection attacks.
**Prevention:** Added `@app_commands.checks.cooldown` to limit users to 1 request every 5 seconds. Implemented input sanitization (removing newlines) before logging user queries.

## 2024-05-25 - Consistent Error Handling
**Vulnerability:** Information Leakage in Error Handling
**Learning:** Security fixes must be applied consistently. A previous fix for information leakage in `play` did not extend to `get_or_connect_player`, leaving a similar vulnerability where connection errors were sent directly to the user.
**Prevention:** Updated `get_or_connect_player` to catch exceptions, log the full error, and send a generic failure message to the user.
