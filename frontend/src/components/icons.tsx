/**
 * A small, deliberately limited set of inline glyphs for the cosmic
 * redesign -- "avoid excessive stars/icons everywhere" per the design
 * brief. Each is used in exactly one place: CrescentStarIcon in the
 * header wordmark; SpreadIcon, BookIcon, ConstellationIcon, and
 * ReflectionIcon (a leaf) as the four major ReadingResultPage
 * SectionPanel header icons (see Panel.tsx's `icon` prop) -- Your
 * Spread, The Reading, Structured Reading, and Your Reflection
 * respectively, matching the approved mockup's own icon set. All four are
 * pure outline/line-art -- `fill="none"` throughout, stroke only, no
 * filled shapes or solid silhouettes anywhere -- so their interior stays
 * transparent/dark, matching the mockup's delicate open-book/leaf glyphs
 * specifically. CrescentStarIcon's own moon now matches that same
 * outline treatment (its star stays solid, deliberately, as the one true
 * accent point in the mark).
 */

/**
 * The header wordmark's logo mark: a thin gold crescent-moon outline and
 * a solid star, flanked by two long thin lines reaching out toward the
 * wordmark's own edges. viewBox widened from the original 64x24 to
 * 140x24 -- same height (so the moon/star cluster's own rendered pixel
 * size is unchanged at any given CSS height, since that mapping is
 * governed by viewBox height alone), but a much longer canvas either side
 * of the cluster so the lines can extend far out rather than stopping
 * just past the glyphs. The moon's path is unchanged from before, only
 * translated sideways to the new canvas center and stroked instead of
 * filled (stroking the same closed crescent path draws its outline).
 */
export function CrescentStarIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 140 24" className={className} fill="none" aria-hidden="true">
      <path d="M2 12h55" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
      <path
        d="M65.5 6.5a7 7 0 1 0 0 11 8.5 8.5 0 1 1 0-11Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path
        d="M76 4.5l1.1 3 3 1.1-3 1.1-1.1 3-1.1-3-3-1.1 3-1.1z"
        fill="currentColor"
      />
      <path d="M83 12h55" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
    </svg>
  )
}

/** Your Spread -- a single four-point sparkle, outline only. No card
 * rectangle: an enclosing box read as a "boxed icon" rather than the
 * delicate line-art the mockup uses, so this is the star motif alone. */
export function SpreadIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3.5c.6 3.8 2.2 6.3 6.5 7-4.3.7-5.9 3.2-6.5 7-.6-3.8-2.2-6.3-6.5-7 4.3-.7 5.9-3.2 6.5-7Z" />
    </svg>
  )
}

/** The Reading -- an open book, two pages meeting at a center spine. */
export function BookIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 6.7c-1.8-1.4-4.1-2.2-6.5-2.2-.6 0-1 .4-1 1v11c0 .6.4 1 1 1 2.4 0 4.7.8 6.5 2.2" />
      <path d="M12 6.7c1.8-1.4 4.1-2.2 6.5-2.2.6 0 1 .4 1 1v11c0 .6-.4 1-1 1-2.4 0-4.7.8-6.5 2.2" />
      <path d="M12 6.7v13.2" opacity="0.6" />
    </svg>
  )
}

/** Structured Reading -- a small constellation, outline dots joined by
 * thin lines (no filled points, so the interior stays transparent like
 * every other section icon). */
export function ConstellationIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 17.5l4.5-8L14 13l5-9.5" opacity="0.6" />
      <circle cx="5" cy="17.5" r="1.3" />
      <circle cx="9.5" cy="9.5" r="1.3" />
      <circle cx="14" cy="13" r="1.3" />
      <circle cx="19" cy="3.5" r="1.3" />
    </svg>
  )
}

/** Your Reflection -- a single leaf with a curved center vein. */
export function ReflectionIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 18.5c-1.6-5.7 1-11.4 11-13.5 1 8.3-3.5 14-11 13.5Z" />
      <path d="M6.6 18C9.1 13.2 12.2 10 16.8 7" opacity="0.6" />
    </svg>
  )
}

/** Bottom-nav glyphs -- Home / Readings / New Reading, matching the
 * app's three real top-level destinations (see BottomNav.tsx). */
export function HomeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 11.5 12 4l8 7.5" />
      <path d="M6 10v9a1 1 0 0 0 1 1h3v-5.5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1V20h3a1 1 0 0 0 1-1v-9" />
    </svg>
  )
}

export function ReadingsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="4" width="7" height="16" rx="1.5" transform="rotate(-6 4 4)" />
      <rect x="13" y="4" width="7" height="16" rx="1.5" transform="rotate(6 20 4)" />
    </svg>
  )
}

export function NewReadingIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 8.2v7.6M8.2 12h7.6" />
    </svg>
  )
}

/** Password-visibility toggle glyphs -- see PasswordInput.tsx. Marked
 * aria-hidden because the toggle button itself carries the accessible
 * name (aria-label="Show password"/"Hide password"). */
export function EyeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.75" />
    </svg>
  )
}

export function EyeOffIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M10.6 5.7A9.9 9.9 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a15.3 15.3 0 0 1-3.05 3.85M7.4 7.15A15.6 15.6 0 0 0 2.5 12s3.5 6.5 9.5 6.5a9.7 9.7 0 0 0 3.35-.6" />
      <path d="M9.9 10.15a2.75 2.75 0 0 0 3.85 3.9" />
    </svg>
  )
}
