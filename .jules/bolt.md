## 2024-05-23 - [Concurrent Voice Connection and Search]
**Learning:** `asyncio.gather` or concurrent `asyncio.create_task` is highly effective when two I/O bound operations (voice connection and API search) are independent.
**Action:** Look for other commands where API calls and Discord interactions can be parallelized.
