"use client";

import { ReactNode, useEffect, useRef } from "react";

/**
 * Adds `is-visible` to its wrapper the first time it enters the viewport.
 * Children opt in with .reveal-item / .reveal-bar / .reveal-dot classes —
 * server components stay server components; this is just a trigger. The
 * class is applied straight to the DOM node (no re-render needed).
 */
export function Reveal({
  children,
  className = "",
  as: Tag = "div"
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "span";
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      node.classList.add("is-visible");
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          node.classList.add("is-visible");
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
     
    <Tag ref={ref as any} className={className}>
      {children}
    </Tag>
  );
}
