/**
 * Smoke test — Stage 2 shared utilities.
 * Tests that Stage 1 utilities still pass after Stage 2 additions.
 */
import { describe, it, expect } from "vitest";
import { cn, capitalise, formatDate } from "./utils";

describe("cn()", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });
  it("resolves Tailwind conflicts", () => {
    expect(cn("px-4", "px-6")).toBe("px-6");
  });
  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });
});

describe("capitalise()", () => {
  it("capitalises the first letter", () => {
    expect(capitalise("hello")).toBe("Hello");
  });
  it("handles empty string", () => {
    expect(capitalise("")).toBe("");
  });
  it("handles already-capitalised", () => {
    expect(capitalise("Hello")).toBe("Hello");
  });
});

describe("formatDate()", () => {
  it("returns a non-empty string for a valid ISO date", () => {
    const result = formatDate("2024-01-15");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });
});
