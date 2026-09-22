/**
 * App-wide night-sky backdrop. Renders once in AppShell, behind every
 * route, as three stacked layers (back to front):
 *
 * 1. SKY_GHOST -- the *same* hero photo file, reused (not duplicated as a
 *    second distinct image) as a `position: fixed` CSS background at a
 *    low constant opacity. Because it's fixed, it's pinned to the
 *    viewport, so `background-size: cover` only ever has to fill one
 *    screen height, never stretched across the scrolling document -- the
 *    thing that caused visible blur in an earlier pass that tried to
 *    stretch an `<img>` to many viewport-heights tall. No filter, no
 *    hue/saturation/contrast/brightness change -- just `opacity`, kept
 *    low (0.16) so it reads as a faint, constant hint that the sky is
 *    still there, never a second focal point next to the hero above it.
 *
 * 2. SKY_GHOST_OCCLUDER -- a plain CSS gradient (no image, so it scales to
 *    any page length with zero quality loss) that starts fully transparent
 *    right where the hero photo's own box ends, then ramps to fully solid
 *    `--color-bg-deepest` over a fixed ~80vh, and stays solid for
 *    whatever's left of the page. This is what makes the ghost layer
 *    "less prominent" as the page scrolls -- it's not the ghost itself
 *    dimming (it's already constant), it's this layer progressively
 *    covering more of it -- and it's what makes the eventual hand-off to
 *    the flat page color read as continuous rather than a cut, since by
 *    the time it reaches full opacity it's already the same solid color
 *    the page uses everywhere else.
 *
 * 3. The hero photograph itself -- public/assets/raidian/
 *    "iss41-milky-way-and-sahara-sands.jpg" (4256x2832), a NASA
 *    astronaut photograph (ISS Expedition 41) of the Milky Way and
 *    starfield above Earth's limb, with ISS hardware silhouettes framing
 *    the frame's edges -- public domain (see
 *    Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md). Same crop,
 *    same fade, no filter of any kind. This is the only layer meant to be
 *    read clearly; layers 1-2 exist purely so the page below it doesn't
 *    feel like a hard cut to flat color.
 *
 * Crop: the outer band is sized with `aspect-4256/2408` (the top ~85% of
 * the photo's natural height, the same fraction every previous pass used
 * for the prior hero photo, re-derived for this photo's own dimensions)
 * while the <img> renders at its own full natural aspect ratio (`w-full
 * h-auto`, never object-fit/upscaling), so the excess simply overflows
 * past the box and `overflow-hidden` clips it there.
 *
 * `import.meta.env.BASE_URL` (never a bare leading slash), matching the
 * existing convention in ../lib/cardArtwork.ts, so this keeps resolving
 * correctly under a GitHub Pages subpath build.
 */

/** Low, constant opacity for the reused-photo ghost layer -- deliberately
 * conservative so it never becomes a second prominent sky next to the
 * hero's own. */
const SKY_GHOST_OPACITY = 0.16

/** Where the occluder's own transparent-to-solid gradient starts: exactly
 * at the hero photo's own box bottom (`100vw * 2408/4256`, the same math
 * the hero's own box height uses), so there's a single, well-defined
 * hand-off point rather than two independent fades overlapping oddly. */
const SKY_CONTINUATION_TOP = 'calc(100vw * 2408 / 4256)'

/** Plain two-stop color gradient (no image, no blur risk at any length)
 * from transparent to the page's own flat `--color-bg-deepest`, over a
 * fixed ~80vh regardless of how long the page is -- vh units (not %) so
 * the transition takes the same real distance on a short page and a long
 * one, rather than stretching proportionally to the box's own height. */
const SKY_CONTINUATION_FADE =
  'linear-gradient(to bottom, transparent 0, transparent 6vh, var(--color-bg-deepest) 80vh, var(--color-bg-deepest) 100%)'

/**
 * A wash toward rgb(11,8,24) -- --color-bg-deepest's deep violet-black --
 * confined to the photo's own lower edge: fully transparent for the first
 * 55% of the box (where the Milky Way and station-hardware silhouettes
 * need to read with the source photo's own contrast, untouched), then
 * ramping up only over the last 45% to ease the image's own coloring
 * toward the page color the alpha mask below is simultaneously fading it
 * into. This is only the fade's *target* color, mirroring
 * --color-bg-deepest so the page transition stays seamless -- the photo
 * itself carries no filter, hue-shift, or overlay.
 */
const HERO_TINT_GRADIENT = [
  'rgba(11,8,24,0) 0%',
  'rgba(11,8,24,0) 55%',
  'rgba(11,8,24,0.1) 72%',
  'rgba(11,8,24,0.24) 85%',
  'rgba(11,8,24,0.4) 100%',
].join(', ')

/** Fades the hero photo (img + tint, masked together) to fully
 * transparent over the last three-quarters of its own box (was the last
 * two-thirds) via an eased curve (extra mid-stops), not a straight linear
 * ramp -- both changes make the dissolve read as gradual atmosphere
 * rather than a perceptible line, even though what's revealed underneath
 * is still just the page's own flat --color-bg-deepest background. */
const HERO_FADE_MASK =
  'linear-gradient(to bottom, black 0%, black 22%, rgba(0,0,0,0.75) 45%, rgba(0,0,0,0.4) 70%, rgba(0,0,0,0.12) 88%, transparent 100%)'

export function CosmicBackground() {
  const heroSrc = `${import.meta.env.BASE_URL}assets/raidian/${encodeURIComponent('iss41-milky-way-and-sahara-sands.jpg')}`

  return (
    <>
      {/* Layer 1: SKY_GHOST -- same photo file, fixed to the viewport, low
          constant opacity. See file doc comment. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-20"
        style={{
          backgroundImage: `url("${heroSrc}")`,
          backgroundSize: 'cover',
          backgroundPosition: 'center top',
          opacity: SKY_GHOST_OPACITY,
        }}
      />

      {/* Layer 2: SKY_GHOST_OCCLUDER -- plain color gradient, no image,
          progressively covers layer 1 until it's solid page color. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 z-[-15]"
        style={{ top: SKY_CONTINUATION_TOP, bottom: 0, backgroundImage: SKY_CONTINUATION_FADE }}
      />

      {/* Layer 3: the hero photo -- same crop/fade/mask treatment as
          every previous pass, re-derived for this photo's own dimensions
          (see file doc comment). */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 aspect-4256/2408 overflow-hidden"
        style={{ WebkitMaskImage: HERO_FADE_MASK, maskImage: HERO_FADE_MASK }}
      >
        {/* No filter/hue-rotate/blend-mode grade on the photo -- shown
            essentially as-is, so the Milky Way's own vividness and the
            station-hardware silhouettes' own contrast are what actually
            render, matching the mockup's clear photographic hierarchy. */}
        <img src={heroSrc} alt="" className="block h-auto w-full" />
        <div
          className="absolute inset-0"
          style={{ backgroundImage: `linear-gradient(to bottom, ${HERO_TINT_GRADIENT})` }}
        />
      </div>
    </>
  )
}
