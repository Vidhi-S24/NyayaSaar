/**
 * Vitest tests for utility functions.
 * These tests are fast and require no network or DOM APIs.
 */
import { describe, it, expect } from "vitest";
import { cn, capitalise } from "@/lib/utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("resolves tailwind conflicts (last wins)", () => {
    expect(cn("p-4", "p-8")).toBe("p-8");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });
});

describe("capitalise", () => {
  it("capitalises first letter", () => {
    expect(capitalise("hello")).toBe("Hello");
  });

  it("leaves already-capitalised strings unchanged", () => {
    expect(capitalise("World")).toBe("World");
  });

  it("handles empty string", () => {
    expect(capitalise("")).toBe("");
  });
});
