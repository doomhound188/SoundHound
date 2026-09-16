import { describe, expect, test } from "bun:test";
import { parseLavalinkUri } from "../src/index";

describe("parseLavalinkUri", () => {
  test("http uri", () => {
    const uri = "http://localhost:2333";
    const result = parseLavalinkUri(uri);
    expect(result).toEqual({ url: "localhost", port: 2333, secure: false });
  });

  test("https uri", () => {
    const uri = "https://secure.lavalink:443";
    const result = parseLavalinkUri(uri);
    expect(result).toEqual({ url: "secure.lavalink", port: 443, secure: true });
  });

  test("no scheme default port", () => {
    const uri = "localhost";
    const result = parseLavalinkUri(uri);
    expect(result).toEqual({ url: "localhost", port: 2333, secure: false });
  });

  test("no scheme custom port", () => {
    const uri = "localhost:8080";
    const result = parseLavalinkUri(uri);
    expect(result).toEqual({ url: "localhost", port: 8080, secure: false });
  });
});
