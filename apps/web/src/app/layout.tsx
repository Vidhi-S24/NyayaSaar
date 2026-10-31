import type { Metadata } from "next";
import "./globals.css";

/**
 * Root layout — NyayaSaar Stage 2.
 *
 * Google Fonts (Inter, Lora, JetBrains Mono) are loaded via next/font/google
 * in production builds with network access. In sandbox/offline environments
 * they fall back to the system font stack via CSS custom properties defined here.
 *
 * To restore Google Fonts in CI or production:
 *   - Import Inter, Lora, JetBrains_Mono from "next/font/google"
 *   - Assign className variables and add them to <html>
 *   - Remove the inline <style> block below
 */

export const metadata: Metadata = {
  title: {
    default: "NyayaSaar",
    template: "%s — NyayaSaar",
  },
  description:
    "Multi-agent legal case intelligence and precedent reasoning platform. For research and reference only — not legal advice.",
  keywords: ["legal research", "case analysis", "precedent", "legal intelligence"],
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/*
         * Font CSS variables — system stacks used as fallbacks.
         * In production with network access, replace with next/font/google imports.
         */}
        <style>{`
          :root {
            --font-inter: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            --font-lora: 'Lora', Georgia, 'Times New Roman', serif;
            --font-jetbrains-mono: 'JetBrains Mono', 'Menlo', 'Monaco', 'Courier New', monospace;
          }
        `}</style>
      </head>
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
