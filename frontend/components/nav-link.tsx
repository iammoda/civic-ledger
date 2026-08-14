"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Nav link that knows whether it's the current section (aria-current +
 * visual state). Client-side only because the active path is per-request;
 * the links themselves render fine before hydration.
 *
 * matchPrefixes: a merged nav section ("What happened") lights up for every
 * route it contains (/votes, /bills, /graveyard) even though it links to one.
 */
export function NavLink({
  href,
  label,
  className,
  activeClassName,
  matchPrefixes
}: {
  href: string;
  label: string;
  className: string;
  activeClassName: string;
  matchPrefixes?: string[];
}) {
  const pathname = usePathname();
  const prefixes = matchPrefixes ?? [href];
  const active =
    href === "/"
      ? pathname === "/"
      : prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`${className}${active ? ` ${activeClassName}` : ""}`}
    >
      {label}
    </Link>
  );
}
