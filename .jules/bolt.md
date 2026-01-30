## 2024-05-23 - [Concurrent Voice Connection and Search]
**Learning:** `asyncio.gather` or concurrent `asyncio.create_task` is highly effective when two I/O bound operations (voice connection and API search) are independent.
**Action:** Look for other commands where API calls and Discord interactions can be parallelized.

## 2024-05-24 - [Input Normalization for Caching]
**Learning:** Whitespace variations in user input (e.g. " song " vs "song") cause cache misses. Normalizing input *before* cache lookup significantly improves hit rates.
**Action:** Always strip/normalize cache keys derived from user input.

## 2024-05-25 - [Asyncio Task Cleanup Safety]
**Learning:** `asyncio.CancelledError` inherits from `BaseException`, not `Exception`. Relying on `except Exception` for cleanup in async functions leaves state corrupted if the task is cancelled.
**Action:** Always use `try...finally` blocks for critical cleanup (like removing pending tasks from a tracking dictionary) to handle success, errors, and cancellation uniformly.

## 2024-05-26 - [Efficient Prefix Checking]
**Learning:** `str.lower().startswith("prefix")` allocates a new string of length `N` (the whole string), which is inefficient for long inputs. `str[:len(prefix)].lower() == "prefix"` allocates only `len(prefix)` (O(1)), saving memory and CPU for checks like `file://`.
**Action:** Use slicing for case-insensitive prefix checks on potentially long strings.
