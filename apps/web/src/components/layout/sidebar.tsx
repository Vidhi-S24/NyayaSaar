"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FolderOpen,
  FileText,
  Brain,
  AlertTriangle,
  Scale,
  Gavel,
  BookOpen,
  History,
  Settings,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const navItems = [
  {
    group: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/cases", label: "Cases", icon: FolderOpen },
      { href: "/documents", label: "Documents", icon: FileText },
    ],
  },
  {
    group: "Intelligence",
    items: [
      { href: "/intelligence", label: "Case Intelligence", icon: Brain },
      { href: "/contradictions", label: "Contradiction & Gap", icon: AlertTriangle },
      { href: "/precedents", label: "Precedent Explorer", icon: BookOpen },
      { href: "/advocate", label: "Advocate Mode", icon: Scale },
      { href: "/judge", label: "Judge / Clerk Mode", icon: Gavel },
    ],
  },
  {
    group: "Records",
    items: [
      { href: "/history", label: "Research History", icon: History },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

interface SidebarProps {
  collapsed?: boolean;
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  const pathname = usePathname();

  return (
    <TooltipProvider delayDuration={0}>
      <nav
        className={cn(
          "flex h-full flex-col border-r border-border bg-card transition-all duration-200",
          collapsed ? "w-14" : "w-60"
        )}
        aria-label="Main navigation"
      >
        {/* Wordmark */}
        <div
          className={cn(
            "flex h-14 shrink-0 items-center border-b border-border px-3",
            collapsed ? "justify-center" : "gap-2.5 px-4"
          )}
        >
          <span
            className="inline-block h-6 w-1 shrink-0 rounded-full bg-teal-600"
            aria-hidden="true"
          />
          {!collapsed && (
            <span className="font-serif text-lg font-semibold tracking-tight text-foreground">
              NyayaSaar
            </span>
          )}
        </div>

        {/* Nav items */}
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
          {navItems.map((group) => (
            <div key={group.group} className="mb-1">
              {!collapsed && (
                <p className="mb-1 px-2 pt-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                  {group.group}
                </p>
              )}
              {collapsed && <div className="my-1 h-px bg-border" />}
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
                const link = (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-2 py-2 text-sm font-medium transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-foreground/70 hover:bg-secondary hover:text-foreground",
                      collapsed && "justify-center px-2"
                    )}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {!collapsed && <span>{item.label}</span>}
                    {!collapsed && isActive && (
                      <ChevronRight className="ml-auto h-3 w-3 opacity-40" aria-hidden="true" />
                    )}
                  </Link>
                );

                if (collapsed) {
                  return (
                    <Tooltip key={item.href}>
                      <TooltipTrigger asChild>{link}</TooltipTrigger>
                      <TooltipContent side="right">{item.label}</TooltipContent>
                    </Tooltip>
                  );
                }
                return link;
              })}
            </div>
          ))}
        </div>

        {/* Disclaimer footer */}
        {!collapsed && (
          <div className="shrink-0 border-t border-border p-3">
            <p className="text-[10px] leading-relaxed text-muted-foreground/50">
              Research tool only. All outputs require professional legal verification.
            </p>
          </div>
        )}
      </nav>
    </TooltipProvider>
  );
}

