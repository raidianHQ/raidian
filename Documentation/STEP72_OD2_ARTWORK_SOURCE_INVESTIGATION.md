# Step 72 — OD-2 Artwork Source & Licensing Investigation

**Status:** Documentation-only. No code, schema, dependency, or image/artwork file was added, changed, or removed in this step. No `image_ref` value was modified. Web research performed for file-level license verification only.

## Decision Status

**Resolved.**

## OD-1 Dependency

OD-1 has been resolved (`Documentation/STEP71_OD1_PRODUCT_DECISION.md`): Spread Review requires actual rendered card artwork; text/tile cards are confirmed as the interim MVP presentation only. This step investigates OD-2 (which artwork source) on that basis. OD-3 (serving/bundling architecture) is a separate, still-open decision, unaffected by this step.

## Governing documentation re-read for this step

- `Documentation/RAIDIAN_WISE_REFERENCE_DATA_V1.md` Sections 5–6: the existing Image-Source Policy (1909 RWS artwork is US public domain; a *specific* modern scan/reprint/colorization may carry its own separate copyright; Wikimedia Commons is named as an example of a plausible verified-public-domain source; file-level verification is required, not a general date-based statement) and the `image_ref` placeholder-path convention.
- `Documentation/CARD_IMAGE_ASSET_DESIGN.md` Sections 2, 3, 5, 6, 11 (re-read directly).
- `Documentation/STEP71_OD1_PRODUCT_DECISION.md` (re-read directly).
- `Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — no artwork-source guidance exists there; confirmed the spec is silent on sourcing (it only ever addresses *whether* imagery is required, which is OD-1, not *which* imagery).
- Current card reference-data YAML (`backend/app/reference_data/rider_waite_smith/*.yaml`): re-confirmed all 78 cards carry a populated `image_ref` placeholder path (14 Wands + 14 Cups + 14 Swords + 14 Pentacles + 22 Major Arcana = 78, recounted directly this step); no actual image files exist anywhere in the repository; no `image_ref` value was touched.

## Candidate Sources Investigated

### 1. Wikimedia Commons — "Rider-Waite-Smith tarot deck (TaionWC)" category

Fetched the category page directly (`commons.wikimedia.org/wiki/Category:Rider-Waite-Smith_tarot_deck_(TaionWC)`):
- Contains exactly **78 files** ("The following 78 files are in this category, out of 78 total") — Major Arcana as `RWS Tarot 00 Fool.jpg` … `RWS Tarot 21 World.jpg`, Minor Arcana as `Cups01.jpg`–`Cups14.jpg`, `Pents01.jpg`–`Pents14.jpg`, `Swords01.jpg`–`Swords14.jpg`, `Wands01.jpg`–`Wands14.jpg`.
- The category's own description states these are scans of the **"Pam-A" version** of the deck, uploaded as a matched set by Commons user **TaionWC**, with an explicit note not to overwrite them with revised scans (Commons' own internal provenance-preservation convention).
- "Pam-A" is independently identifiable, not a project-invented label: corroborated by a separate tarot-deck cataloguing source (`etteilla.org/en/deck/81/original-waite-smith-tarot-pam-a`), which describes Pam-A as the **1910 UK "Rider" trade printing**, distinguishable from later printings by concrete physical characteristics — a distinctive line-based (rather than halftone-dot) color-printing technique, and a specific line artifact near the top of the Sun card. This is a real, specific, identifiable print-run, not a vague "circa 1909" claim.

**Sampled individual file pages (verified directly, not inferred from the category blurb):**
- `File:Cups09.jpg` — Author: Pamela Colman Smith (1878–1951); Date: 1910; Source: `muzendo.jp/blog/`; Categories include "Rider-Waite-Smith tarot deck (TaionWC)". Licensing: **two explicit public-domain tags** — (a) public domain based on the death of the credited copyright holder, Arthur Edward Waite, in 1942 (life-plus-80-or-fewer jurisdictions), and (b) public domain in the United States as published before January 1, 1931 — plus the Creative Commons Public Domain Mark 1.0 applied by Commons itself.
- `File:RWS Tarot 00 Fool.jpg` — same author, same 1910 date, same `muzendo.jp/blog/` source, same dual PD-tag pattern, same CC PD Mark 1.0.

Both sampled files show **identical, internally consistent, specifically-reasoned** licensing — not a bare "public domain" assertion with no basis.

### 2. Wikimedia Commons — "Rider-Waite-Smith tarot deck (Geldard)" category

Also claims 78 files and complete-deck coverage. However, the category page itself provided materially less documentation: only a note that images were "cleaned and uploaded by YarnSpinnerTool," no description of what "Geldard" refers to (edition, source, or scanner), and no license/source statement at the category level. Individual file pages in this set were not sampled in this step (time/scope-bounded) given the TaionWC set already provided a materially stronger, directly-verified trail. **Not disqualified — simply not verified to the same standard in this step.**

### 3. Internet Archive — `archive.org/details/rider-waite-tarot`

78 PNG files, "400+dpi resolution scan," uploaded by user `abetusk`, tagged "Public Domain Mark 1.0." Fetched directly: **no statement of which printing/edition/physical deck was scanned**, and no stated basis for the public-domain tag beyond the uploader's own assertion. This is exactly the pattern the repository's policy warns against — a collection-level PD tag with no identified source edition, which cannot be distinguished from a scan of a modern, separately-copyrighted reprint. **Not selected**, for lack of file/edition-level provenance, not because public domain status is doubted outright.

### Other candidates noted, not selected

- Wikimedia Commons "Rider-Waite tarot deck (Roses & Lilies)" and "The Pictorial Key to the Tarot" subcategories exist but represent different printings/purposes (e.g. the black-and-white companion-book illustrations, not a full-color 78-card deck set) and were not investigated further, since TaionWC already satisfied the "complete 78-card set with individually-verified licensing" bar.
- `sacred-texts.com`'s dedicated "Rider-Waite-Smith Tarot Card Copyright FAQ" could not be fetched directly (HTTP 403 on both the primary domain and an `archive.sacred-texts.com` mirror). A partial fetch of a third-party mirror (`spiritmaji.com/sacredtext/tarot/faq.htm`) returned only its table of contents, not full answers, but confirmed the FAQ specifically discusses **US Games Systems' 1971 copyright notice and trademark claims** on their own modern commercial reprint of the deck — real, concrete corroboration (not a generic warning) of exactly the "a specific modern scan/reprint can carry its own separate copyright" risk the repository's own policy already names. This reinforces why the *specific* Pam-A/1910 print run matters and why a generic "1909 is public domain" statement would not have been sufficient.

## File-Level Licensing Evidence

| Candidate | Exact artwork/source | 78 cards? | File-level rights evidence | License/public-domain basis | Attribution | Redistribution | Stable access | Notes |
|---|---|---:|---|---|---|---|---|---|
| Wikimedia Commons — "Rider-Waite-Smith tarot deck (TaionWC)" | "Pam-A" 1910 Rider (UK) trade-edition scan, source cited as `muzendo.jp/blog/` | Yes (78/78, confirmed at category level) | 2 of 78 individual file pages directly sampled; both showed identical, specific, dual-basis PD tags, not a bare assertion | (a) Life of credited copyright holder A. E. Waite, d. 1942, life-plus-80-or-fewer jurisdictions; (b) Published before Jan 1, 1931 — US public domain; CC PD Mark 1.0 applied by Commons | Not legally required (PD Mark); author/source metadata present on file pages if voluntary attribution is desired | Commons' PD Mark permits redistribution and modification with no restriction stated | Stable, individually-addressable file URLs per card, long-established Commons hosting | Strongest candidate; not all 78 files individually re-verified in this step |
| Wikimedia Commons — "Rider-Waite-Smith tarot deck (Geldard)" | Unidentified specific edition; "cleaned and uploaded by YarnSpinnerTool" | Claimed yes (78/78 at category level) | Category-level only; no individual file pages sampled this step | Not stated at category level | Unknown | Unknown | Presumed stable (Commons-hosted) but undocumented | Not selected — insufficient documentation trail relative to TaionWC, not proven unsuitable |
| Internet Archive — `rider-waite-tarot` (abetusk) | Unidentified scan source/edition; "400+dpi resolution scan" | Claimed yes (78 files) | Item-level "Public Domain Mark 1.0" tag with no stated basis or source edition | Not stated — cannot confirm this isn't a scan of a modern, separately-copyrighted reprint | Not stated | Presumed permitted per PD Mark, but basis unverified | Item page stable; direct-file access format unconfirmed | Not selected — exactly the "unverified modern-scan" risk the repo's own policy warns against |

## Selected Source

**Wikimedia Commons — "Rider-Waite-Smith tarot deck (TaionWC)" category** (`commons.wikimedia.org/wiki/Category:Rider-Waite-Smith_tarot_deck_(TaionWC)`), representing the "Pam-A" 1910 Rider (UK) trade-edition scan of the Pamela Colman Smith / Arthur Edward Waite deck, is the **approved candidate source** for Raidian Wise artwork.

**Verification date:** 2026-09-19 (this step).

**Authoritative links (as verified this step):**
- Category: `https://commons.wikimedia.org/wiki/Category:Rider-Waite-Smith_tarot_deck_(TaionWC)`
- Sampled file: `https://commons.wikimedia.org/wiki/File:Cups09.jpg`
- Sampled file: `https://commons.wikimedia.org/wiki/File:RWS_Tarot_00_Fool.jpg`

**Limitations and caveats (explicit, not glossed over):**
- Only 2 of the 78 individual file pages were directly sampled; the remaining 76 were not individually re-verified in this step. The category's own framing (a matched set, uploaded together, with a "do not overwrite" provenance-preservation note) supports an inference of consistency, but this is an inference, not 78-for-78 direct verification.
- The public-domain determination rests on Wikimedia Commons' own community-applied license tags (citing A. E. Waite's 1942 death and pre-1931 US publication), not on independent legal counsel obtained by this project. This is consistent with how the repository's existing policy already treats Commons (as "an example of a plausible verified-public-domain source"), but it is not a substitute for legal advice if that level of certainty is ever required.
- The ultimate scan source cited on sampled file pages (`muzendo.jp/blog/`) is a blog, not an archival institution — this affects confidence in the *scan's own chain of custody/quality*, not the underlying public-domain status of the 1910 artwork itself, which rests on the Waite-death/pre-1931 legal basis independent of who scanned it.

## Attribution / Redistribution Requirements

No attribution is legally required under the Creative Commons Public Domain Mark 1.0 applied to the sampled files. Voluntary attribution information is available on each file page (Pamela Colman Smith as illustrator, 1910 date, Wikimedia Commons as host) if Raidian Wise chooses to credit it anyway (a product-taste choice, not a legal requirement — not decided by this step). Redistribution and modification both appear permitted under the PD Mark with no stated restriction.

## What This Does NOT Decide

- OD-3 remains open — no serving/bundling architecture has been selected.
- No image files have been added to this repository.
- No frontend rendering has been implemented.
- `image_ref` values remain untouched (still the original logical placeholder paths).
- No dependency, backend change, or schema change was made.

## Next Dependency

> Proceed to OD-3 — determine how the verified artwork assets should be packaged and served (see `Documentation/CARD_IMAGE_ASSET_DESIGN.md` Section 6, Options A–D, for the architecture candidates already evaluated but not yet decided).
