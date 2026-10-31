"use client";

import { useState } from "react";
import { Sidebar } from "./sidebar";
import { TopBar } from "./topbar";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
}

export function AppShell({ children, title }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar — desktop */}
      <div className="hidden lg:flex lg:shrink-0">
        <Sidebar collapsed={collapsed} />
      </div>

      {/* Sidebar — mobile drawer */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 lg:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          "transition-transform duration-200"
        )}
      >
        <Sidebar />
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar
          onMenuToggle={() => setMobileOpen((v) => !v)}
          title={title}
        />
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

