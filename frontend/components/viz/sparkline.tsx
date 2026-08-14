/**
 * Tiny inline bar chart (SVG) for a short series — e.g. an MP's office
 * spending by quarter. No axes, no library: the shape is the message,
 * exact values live in text next to it.
 */
export function Sparkline({
  values,
  className = "",
  width = 120,
  height = 32,
  highlightLast = true
}: {
  values: number[];
  className?: string;
  width?: number;
  height?: number;
  highlightLast?: boolean;
}) {
  if (!values.length) return null;
  const max = Math.max(...values, 1);
  const gap = 2;
  const barWidth = (width - gap * (values.length - 1)) / values.length;
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden
    >
      {values.map((value, i) => {
        const h = Math.max(2, (value / max) * height);
        const last = highlightLast && i === values.length - 1;
        return (
          <rect
            key={i}
            x={i * (barWidth + gap)}
            y={height - h}
            width={barWidth}
            height={h}
            rx={1}
            className={last ? "fill-accent" : "fill-slate-300"}
          />
        );
      })}
    </svg>
  );
}
