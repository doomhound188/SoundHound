import { URL } from "node:url";

// Max Queue Size to prevent memory exhaustion
export const MAX_QUEUE_SIZE = 500;
// Max Cache Size for search queries
export const MAX_CACHE_SIZE = 100;

class LRUCache<K, V> {
  private capacity: number;
  private cache: Map<K, V>;

  constructor(capacity: number) {
    this.capacity = capacity;
    this.cache = new Map();
  }

  get(key: K): V | undefined {
    if (!this.cache.has(key)) return undefined;
    const value = this.cache.get(key)!;
    // Move to end (most recently used)
    this.cache.delete(key);
    this.cache.set(key, value);
    return value;
  }

  set(key: K, value: V) {
    if (this.cache.has(key)) {
      this.cache.delete(key);
    }
    this.cache.set(key, value);
    if (this.cache.size > this.capacity) {
      // Remove the first (oldest) item
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey !== undefined) {
        this.cache.delete(oldestKey);
      }
    }
  }

  has(key: K): boolean {
    return this.cache.has(key);
  }

  clear() {
    this.cache.clear();
  }
}

const searchCache = new LRUCache<string, any>(MAX_CACHE_SIZE);
const pendingSearches = new Map<string, Promise<any>>();

export async function validateQuery(query: string): Promise<string> {
  if (!query) {
    throw new Error("Query cannot be empty.");
  }

  if (query.length > 1000) {
    throw new Error("Query is too long (max 1000 characters).");
  }

  query = query.trim();
  if (!query) {
    throw new Error("Query cannot be empty.");
  }

  if (query.slice(0, 7).toLowerCase() === "file://") {
    throw new Error("This protocol is not supported for security reasons.");
  }

  const lowerQuery = query.toLowerCase();
  if (lowerQuery.startsWith("http://") || lowerQuery.startsWith("https://")) {
    let hostname: string | null = null;
    try {
      const parsed = new URL(query);
      hostname = parsed.hostname;
    } catch (e) {
      // Fallback or ignore parse errors as in Python version
    }

    if (hostname) {
      const blockedHosts = new Set(["localhost", "127.0.0.1", "::1", "0.0.0.0", "169.254.169.254"]);
      // Also need to strip ipv6 brackets
      const strippedHostname = hostname.replace(/^\[|\]$/g, "");
      if (blockedHosts.has(strippedHostname.toLowerCase())) {
        throw new Error("This host is blocked for security reasons.");
      }
    }
  }

  return query;
}

export async function searchWithCache(query: string, searchFn: (query: string) => Promise<any>): Promise<any> {
  const cached = searchCache.get(query);
  if (cached !== undefined) {
    return cached;
  }

  if (pendingSearches.has(query)) {
    return pendingSearches.get(query);
  }

  const task = searchFn(query);
  pendingSearches.set(query, task);

  try {
    const results = await task;
    searchCache.set(query, results);
    return results;
  } finally {
    pendingSearches.delete(query);
  }
}

// Exposed for testing
export const _searchCache = searchCache;
export const _pendingSearches = pendingSearches;
