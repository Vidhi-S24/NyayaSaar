"use client";

import { useEffect, useRef, useState } from "react";
import { LogOut, Search, HelpCircle, Menu, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useAuth } from "@/lib/auth/auth-context";
import { userInitials } from "@/lib/api/cases";

interface TopBarProps {
  onMenuToggle?: () => void;
  title?: string;
}

export function TopBar({ onMenuToggle, title }: TopBarProps) {
  const { user, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close the account menu on outside click or Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const initials = user ? userInitials(user) : "—";

  return (
    <TooltipProvider delayDuration={0}>
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
        {/* Mobile menu */}
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          onClick={onMenuToggle}
          aria-label="Toggle navigation"
        >
          <Menu className="h-4 w-4" />
        </Button>

        {/* Page title on mobile */}
        {title && (
          <span className="font-medium text-foreground lg:hidden">{title}</span>
        )}

        {/* Search */}
        <div className="relative hidden flex-1 max-w-sm lg:flex">
          <Search
            className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            placeholder="Search cases, documents…"
            className="pl-8 text-sm h-8 bg-background"
            aria-label="Search"
          />
        </div>

        <div className="ml-auto flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Help">
                <HelpCircle className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Help &amp; documentation</TooltipContent>
          </Tooltip>

          {/* Account menu */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="ml-1 flex h-8 items-center gap-1.5 rounded-full bg-ink-800 pl-1 pr-2 text-xs font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Account menu"
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink-700 text-[10px]">
                {initials}
              </span>
              <ChevronDown className="h-3 w-3 opacity-70" aria-hidden="true" />
            </button>

            {menuOpen && (
              <div
                role="menu"
                aria-label="Account"
                className="absolute right-0 top-10 z-50 w-56 overflow-hidden rounded-md border border-border bg-card shadow-md"
              >
                <div className="border-b border-border px-3 py-2.5">
                  <p className="truncate text-xs font-medium text-foreground">
                    {user?.full_name ?? user?.email}
                  </p>
                  {user?.full_name && (
                    <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{user.email}</p>
                  )}
                </div>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    signOut();
                  }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-xs text-foreground transition-colors hover:bg-secondary focus-visible:bg-secondary focus-visible:outline-none"
                >
                  <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>
    </TooltipProvider>
  );
}
