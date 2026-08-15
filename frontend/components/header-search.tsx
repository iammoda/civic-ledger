"use client";

import { useEffect, useRef } from "react";

/**
 * Header search: fixed width (no focus jump), a real search glyph, and a
 * "/" keyboard shortcut. Submits to /search — works without JS too.
 */
export function HeaderSearch() {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // "/" focuses search unless the user is already typing somewhere.
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (target?.isContentEditable) return;
      event.preventDefault();
      inputRef.current?.focus();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <form action="/search" method="get" className="relative hidden md:block">
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-stone-400"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
      <input
        ref={inputRef}
        type="search"
        name="q"
        placeholder="Search the record…"
        aria-label="Search"
        minLength={2}
        required
        className="w-60 rounded-full border border-border bg-white py-1.5 pl-9 pr-8 text-sm outline-none transition focus:border-accent"
      />
      <kbd
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded border border-border bg-surface px-1.5 font-sans text-[10px] font-semibold text-stone-400"
      >
        /
      </kbd>
    </form>
  );
}
