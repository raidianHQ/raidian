import type { ElementType, ReactNode } from 'react'

/**
 * Shared translucent panel chrome -- dark purple surface, thin gold
 * border, soft rounded corners, subtle lift -- used across every page so
 * the cosmic redesign reads as one design system rather than a single
 * restyled page (ReadingResultPage) sitting inside an otherwise-default
 * app. See also GoldDivider for the transition between two Panels.
 *
 * bg-panel/90, no backdrop-blur: earlier passes chased transparency (down
 * to /55, with and without blur) on the theory that the panel needed to
 * show the photographic sky through it to feel like it belongs to the
 * scene. The reference mockup's board isn't transparent -- it reads as
 * part of the environment because it's the *same color family* as the
 * sky's own palette and the page background behind it, not because stars
 * show through the glass. So the panel is close to solid, and blur is
 * dropped entirely since there's no longer any background detail
 * underneath it worth softening.
 *
 * --color-panel is its own token (currently the same value as
 * --color-paper-muted, the deep violet/plum "secondary/muted purple
 * surface") rather than reusing --color-paper-muted directly, so the
 * board's surface color can be tuned independently of every other place
 * --color-paper-muted is used (card slots, badges, etc. across
 * ReadingResultPage/CardEntryPage/etc.) without touching those.
 *
 * `as` lets a Panel also be the semantic element a section needs (e.g.
 * `as="section"`) instead of always rendering a bare div.
 */
export function Panel({
  children,
  className = '',
  as: Tag = 'div',
}: {
  children: ReactNode
  className?: string
  as?: ElementType
}) {
  return (
    <Tag
      className={`rounded-3xl border border-border bg-panel/90 p-5 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.7)] sm:p-8 ${className}`}
    >
      {children}
    </Tag>
  )
}

/** Small tracked-out gold label introducing a Panel's contents. */
export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="mb-4 text-xs font-medium tracking-[0.25em] text-accent uppercase">{children}</p>
}

/**
 * A major-experience Panel with its own two-tier background: this same
 * translucent bg-panel/90 body, plus a distinctly darker, fully opaque
 * header band across the top holding the section's optional icon and
 * title side by side, as one centered horizontal group, in large serif
 * type -- not a separate bordered banner, just a flat color step, clipped
 * to the panel's own rounded corners via `overflow-hidden`, so the title
 * reads as part of the panel's own architecture rather than text sitting
 * on top of its content.
 *
 * The header band uses --color-paper (the same rich dark purple as the
 * journal/reflection textarea's own background) rather than
 * --color-bg-deepest -- that was the page's own darkest tone, which made
 * the header read as a near-black strip sitting on top of the panel
 * instead of an integrated part of it. --color-paper sits between the
 * page background and the lighter --color-panel body, giving a clear
 * three-step depth: page (darkest) -> header band (richer dark purple,
 * same depth as the journal input) -> body (lighter panel surface).
 *
 * The header also carries a "reflected edge" gold treatment -- two thin
 * gradient hairlines (transparent at the true edges, brightest toward the
 * middle) absolutely positioned at the header's own top and bottom, plus
 * a tiny diamond ornament centered on the top one. Both are `absolute`
 * with zero layout height of their own, so they add the accent language
 * from the mockup's illuminated section dividers without making the
 * header any taller -- the bottom hairline in particular is what visually
 * "connects" the header band to the lighter panel body beneath it, in
 * place of an abrupt flat color cut.
 *
 * Reserved for genuinely major sections (ReadingResultPage: Your Spread,
 * The Reading, Structured Reading, Your Reflection) -- smaller
 * subsections within one of those (Key Themes, Card by Card, ...) use
 * plain typography/dividers instead, never their own SectionPanel, so
 * this treatment stays meaningful rather than every subsection looking
 * like its own panel.
 */
export function SectionPanel({
  title,
  icon,
  children,
  className = '',
}: {
  title: string
  icon?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`overflow-hidden rounded-3xl border border-border bg-panel/90 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.7)] ${className}`}
    >
      <div className="relative flex items-center justify-center gap-3 bg-paper px-5 py-5 text-center sm:px-8 sm:py-6">
        <span
          aria-hidden="true"
          className="absolute inset-x-10 top-0 h-px bg-linear-to-r from-transparent via-accent/70 to-transparent sm:inset-x-16"
        />
        <span
          aria-hidden="true"
          className="absolute top-0 left-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rotate-45 bg-accent"
        />
        {icon}
        <h2 className="font-serif text-2xl tracking-wide text-ink sm:text-3xl">{title}</h2>
        <span
          aria-hidden="true"
          className="absolute inset-x-10 bottom-0 h-px bg-linear-to-r from-transparent via-accent/40 to-transparent sm:inset-x-16"
        />
      </div>
      <div className="flex flex-col gap-8 p-5 sm:p-8">{children}</div>
    </section>
  )
}
