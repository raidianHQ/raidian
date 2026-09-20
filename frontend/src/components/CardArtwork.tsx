import { useState } from 'react'
import type { CardSummary } from '../api/cards'
import type { Orientation } from '../api/readings'
import { orientationLabel, resolveCardArtwork } from '../lib/cardArtwork'

/**
 * Shared card artwork rendering (Step 75), extracted from
 * SpreadReviewPage so ReadingResultPage's own card-by-card presentation
 * can reuse the exact same resolution/fallback logic rather than a second,
 * possibly-diverging copy. Path resolution itself lives in
 * ../lib/cardArtwork.ts.
 *
 * Renders a drawn card's artwork, upright always -- the source scan
 * itself is never rotated; reversed orientation is communicated only via
 * a separate text/badge indicator alongside it, never by transforming the
 * image. Falls back to a calm, text-only placeholder (no broken-image
 * icon, no API request) if `image_ref` is absent or the resolved asset
 * fails to load.
 */
export function CardArtwork({ card, orientation }: { card: CardSummary; orientation: Orientation }) {
  const [failed, setFailed] = useState(false)
  const src = resolveCardArtwork(card.image_ref)

  if (!src || failed) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-1 rounded-md bg-paper-muted px-2 py-3 text-center">
        <span className="text-xs text-ink-soft">Artwork unavailable</span>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={`${card.name} — ${orientationLabel(orientation)}`}
      onError={() => setFailed(true)}
      className="h-full w-full rounded-md object-contain"
    />
  )
}
