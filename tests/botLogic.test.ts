import { describe, expect, test, beforeEach, mock } from "bun:test";
import { validateQuery, searchWithCache, _searchCache, _pendingSearches, MAX_CACHE_SIZE } from "../src/botLogic";

describe("validateQuery", () => {
  test("valid query", async () => {
    const query = "valid query";
    const result = await validateQuery(query);
    expect(result).toBe(query);
  });

  test("strips whitespace", async () => {
    const query = "  valid query  ";
    const result = await validateQuery(query);
    expect(result).toBe("valid query");
  });

  test("empty query", async () => {
    expect(validateQuery("")).rejects.toThrow("Query cannot be empty.");
    expect(validateQuery("   ")).rejects.toThrow("Query cannot be empty.");
  });

  test("too long", async () => {
    const query = "a".repeat(1001);
    expect(validateQuery(query)).rejects.toThrow("Query is too long (max 1000 characters).");
  });

  test("blocks file protocol", async () => {
    expect(validateQuery("file:///etc/passwd")).rejects.toThrow("This protocol is not supported for security reasons.");
    expect(validateQuery("FILE:///etc/passwd")).rejects.toThrow("This protocol is not supported for security reasons.");
  });

  test("blocks localhost", async () => {
    expect(validateQuery("http://localhost:8080/secret")).rejects.toThrow("This host is blocked for security reasons.");
  });

  test("blocks loopback ip", async () => {
    expect(validateQuery("http://127.0.0.1:8080")).rejects.toThrow("This host is blocked for security reasons.");
  });

  test("blocks ipv6 loopback", async () => {
    expect(validateQuery("http://[::1]")).rejects.toThrow("This host is blocked for security reasons.");
  });

  test("blocks metadata service", async () => {
    expect(validateQuery("http://169.254.169.254/latest/meta-data/")).rejects.toThrow("This host is blocked for security reasons.");
  });

  test("allows external url", async () => {
    const query = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
    const result = await validateQuery(query);
    expect(result).toBe(query);
  });
});

describe("searchWithCache", () => {
  beforeEach(() => {
    _searchCache.clear();
    _pendingSearches.clear();
  });

  test("search cache hit", async () => {
    const query = "cached song";
    const mockResult = ["track1", "track2"];
    const mockSearchFn = mock(async () => mockResult);

    // First call: Cache miss
    const res1 = await searchWithCache(query, mockSearchFn);
    expect(res1).toBe(mockResult);
    expect(mockSearchFn).toHaveBeenCalledTimes(1);

    // Second call: Cache hit
    const res2 = await searchWithCache(query, mockSearchFn);
    expect(res2).toBe(mockResult);
    expect(mockSearchFn).toHaveBeenCalledTimes(1); // Not called again
  });

  test("search cache miss different queries", async () => {
    const query1 = "song A";
    const query2 = "song B";
    let callCount = 0;
    const mockSearchFn = mock(async (q: string) => {
      callCount++;
      return [q];
    });

    await searchWithCache(query1, mockSearchFn);
    await searchWithCache(query2, mockSearchFn);
    expect(callCount).toBe(2);
  });

  test("search coalescing", async () => {
    const query = "coalesce_me";
    let callCount = 0;

    const mockSearchFn = mock(async () => {
      callCount++;
      await new Promise(resolve => setTimeout(resolve, 10)); // simulate delay
      return ["result"];
    });

    const t1 = searchWithCache(query, mockSearchFn);
    const t2 = searchWithCache(query, mockSearchFn);

    const [res1, res2] = await Promise.all([t1, t2]);

    expect(res1).toEqual(["result"]);
    expect(res2).toEqual(["result"]);
    expect(callCount).toBe(1); // Should only be called once
  });
});
