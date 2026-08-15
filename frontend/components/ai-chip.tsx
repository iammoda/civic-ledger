/** Small "AI" chip marking AI-generated org descriptions. One source of truth. */
export function AiChip() {
  return (
    <span
      title="AI-generated description — may contain errors"
      className="inline-flex shrink-0 items-center rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-stone-500"
    >
      AI
      <span className="sr-only"> — AI-generated description, may contain errors</span>
    </span>
  );
}
