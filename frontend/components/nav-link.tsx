"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/**
 * Nav link that knows whether it's the current section (aria-current +
 * visual state). Client-side only because the active path is per-request;
 * the links themselves render fine before hydration.
 */
export function NavLink({
  href,
  label,
  className,
  activeClassName
}: {
  href: string;
  label: string;
  className: string;
  activeClassName: string;
}) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
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
