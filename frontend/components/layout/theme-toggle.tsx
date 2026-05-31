"use client";

import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Light/dark switch. Icon visibility is driven by the `.dark` class (set by
 * next-themes' pre-paint script) via CSS, so both icons are always in the DOM —
 * no `mounted` effect, no hydration mismatch, no flash.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { setTheme, resolvedTheme } = useTheme();

  return (
    <button
      type="button"
      aria-label="Toggle dark mode"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      className={cn(
        "inline-flex size-8 items-center justify-center rounded-full border border-sidebar-border text-sidebar-foreground/70 transition-transform hover:text-sidebar-foreground active:scale-95",
        className,
      )}
    >
      <Sun className="hidden size-4 dark:block" />
      <Moon className="size-4 dark:hidden" />
    </button>
  );
}
