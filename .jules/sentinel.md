# Sentinel's Journal

## 2024-05-23 - Input Validation and Information Leakage
**Vulnerability:** Input Validation (DoS) and Information Leakage
**Learning:** The `play` command accepted queries of arbitrary length, which could potentially lead to DoS. Additionally, exception messages were being sent directly to the user, potentially leaking internal details.
**Prevention:** Implemented input length validation (max 1000 characters) for search queries. Also sanitized error messages sent to the user while logging full errors to the console.
