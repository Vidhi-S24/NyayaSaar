/**
 * Utility: merge Tailwind class names safely.
 * Uses clsx + tailwind-merge so conflicting utilities are resolved correctly.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a date string to a readable locale format.
 */
export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/**
 * Capitalise the first letter of a string.
 */
export function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

