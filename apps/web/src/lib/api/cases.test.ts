import { describe, it, expect } from "vitest";
import { userInitials, formatRelativeTime } from "@/lib/api/cases";

describe("userInitials", () => {
  it("returns first + last initial from a full name", () => {
    expect(userInitials({ full_name: "A. Sharma", email: "a@example.com" })).toBe("AS");
  });

  it("returns first initial only for single-word names", () => {
    expect(userInitials({ full_name: "Vidhi", email: "v@example.com" })).toBe("V");
  });

  it("falls back to the first two letters of the email", () => {
    expect(userInitials({ full_name: null, email: "advocate@chambers.in" })).toBe("AD");
  });

  it("returns ? when name and email are empty", () => {
    expect(userInitials({ full_name: "", email: "" })).toBe("?");
  });
});

describe("formatRelativeTime", () => {
  it("returns 'just now' for timestamps within a minute", () => {
    const now = new Date().toISOString();
    expect(formatRelativeTime(now)).toBe("just now");
  });

  it("returns minutes for recent timestamps", () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(formatRelativeTime(fiveMinutesAgo)).toBe("5m ago");
  });

  it("returns hours for same-day timestamps", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3_600_000).toISOString();
    expect(formatRelativeTime(threeHoursAgo)).toBe("3h ago");
  });

  it("returns a date string for invalid input without throwing", () => {
    expect(formatRelativeTime("not-a-date")).toBe("");
  });
});
