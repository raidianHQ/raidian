/**
 * The gold divider between distinct experiences on a page -- most
 * importantly between ReadingResultPage.tsx's major SectionPanels (see
 * Panel.tsx) (Documentation redesign brief: "Do not simply place both
 * sections into one large undifferentiated card").
 *
 * `fromLabel`/`toLabel` are optional so the same divider also works as a
 * lighter, unlabeled separator between sections that don't need naming.
 *
 * `size="lg"` (default "sm") is for transitions between *major* sections
 * specifically -- more vertical space around it and a larger center
 * ornament, so it reads as a deliberate stage break rather than merely a
 * bigger rule.
 *
 * The line row is a percentage width (92%/90%), not a fixed `max-w-*` --
 * a fixed cap is what made earlier passes of this divider look short next
 * to an 1100px-wide SectionPanel no matter how much vertical space or
 * ornament size was added around it. At this width the lines read as an
 * extension of the panel's own edges rather than a small decoration
 * floating in the middle of the page, while still leaving a consistent
 * margin on both sides. The gradient's peak color is `accent` (not the
 * fainter `border` token, which was tuned down for repeated small card
 * borders elsewhere and reads as too faint at this length) so the line
 * stays clearly visible while still fading to nothing at both true ends --
 * the "reflected edge" glow rather than a flat CSS border.
 */
export function GoldDivider({
  fromLabel,
  toLabel,
  size = 'sm',
}: {
  fromLabel?: string
  toLabel?: string
  size?: 'sm' | 'lg'
}) {
  const isLarge = size === 'lg'
  return (
    <div
      role="separator"
      aria-hidden="true"
      className={`flex flex-col items-center gap-3 ${isLarge ? 'py-10 sm:py-14' : 'my-2 py-6'}`}
    >
      {fromLabel && (
        <span className="font-serif text-xs tracking-[0.3em] text-accent uppercase">{fromLabel}</span>
      )}
      <div className={`flex items-center gap-3 ${isLarge ? 'w-[94%] sm:w-[92%]' : 'w-[90%] sm:w-[88%]'}`}>
        <span className="h-px flex-1 bg-linear-to-r from-transparent to-accent/65" />
        <span
          className={`flex shrink-0 items-center justify-center rounded-full border border-border text-accent ${
            isLarge ? 'h-10 w-10' : 'h-6 w-6'
          }`}
        >
          <svg
            viewBox="0 0 16 16"
            className={isLarge ? 'h-4 w-4' : 'h-3 w-3'}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M4 6l4 4 4-4" />
          </svg>
        </span>
        <span className="h-px flex-1 bg-linear-to-l from-transparent to-accent/65" />
      </div>
      {toLabel && <span className="font-serif text-xs tracking-[0.3em] text-accent uppercase">{toLabel}</span>}
    </div>
  )
}
