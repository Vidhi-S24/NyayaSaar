"use client";

import { Bell, Search, HelpCircle, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface TopBarProps {
  onMenuToggle?: () => void;
  title?: string;
}

export function TopBar({ onMenuToggle, title }: TopBarProps) {
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

          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Notifications" className="relative">
                <Bell className="h-4 w-4" />
                <span
                  className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-teal-500"
                  aria-hidden="true"
                />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Notifications</TooltipContent>
          </Tooltip>

          {/* Avatar */}
          <button
            className="ml-1 flex h-8 w-8 items-center justify-center rounded-full bg-ink-800 text-xs font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Account menu"
          >
            VS
          </button>
        </div>
      </header>
    </TooltipProvider>
  );
}

