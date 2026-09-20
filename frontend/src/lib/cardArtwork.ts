import type { Orientation } from '../api/readings'

/**
 * Card artwork path resolution (Step 75) -- plain helpers, kept out of
 * components/CardArtwork.tsx so that component file can export only its
 * component (react-refresh/only-export-components).
 *
 * `image_ref` (e.g. "rws/wands/four-of-wands.png") stays exactly as the
 * database/seed data defines it -- this only derives where the already-
 * acquired bundled asset lives for it, purely a frontend rendering
 * concern. `import.meta.env.BASE_URL` (never a bare leading slash) so the
 * result stays correct under a future GitHub Pages subpath deploy.
 */
export function resolveCardArtwork(imageRef: string | null): string | null {
  if (!imageRef) {
    return null
  }
  const bundledPath = imageRef.replace(/\.png$/i, '.jpg')
  return `${import.meta.env.BASE_URL}cards/${bundledPath}`
}

export function orientationLabel(orientation: Orientation): string {
  return orientation === 'reversed' ? 'Reversed' : 'Upright'
}
