# Step 71 — OD-1 Product Decision: Spread Review Artwork

**Status:** Documentation-only. No code, schema, dependency, or artwork file was added, changed, or removed in this step.

## Decision

Actual card artwork is required on Spread Review.

## Product-owner intent

Quoted exactly, as given for this step:

> "Spread Review must display actual card artwork. The Product Spec's wording 'full visual layout of all positions, cards, and orientations' is intended to include rendered card artwork/images. Text-only card tiles are not the final intended presentation."

## Scope

This decision resolves OD-1 as originally defined in `Documentation/CARD_IMAGE_ASSET_DESIGN.md` Section 11: whether Spread Review's Product Spec requirement ("full visual layout of all positions, cards, and orientations," "all cards visible") requires rendered card artwork. It applies **specifically to Spread Review**.

It does **not** retroactively change Card Entry's separate scope. Card Entry's "visual card browsing" remains explicitly deferred Future Scope per `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Sections 18–19, unaffected by this decision — Card Entry is a searchable/filterable selector by design, a different screen with its own, already-settled requirement text. Nothing about this decision implies Card Entry must also render artwork.

## Consequences

- Current text tiles remain acceptable as the temporary implementation until artwork work is completed. The already-released `v0.2.0-mvp` baseline is not retroactively invalidated by this decision — it shipped correctly under the state of knowledge at the time (OD-1 was genuinely unresolved then).
- Future Spread Review implementation must render actual card artwork.
- Orientation must remain visible/understandable (upright vs. reversed), however artwork is ultimately rendered.
- OD-2 remains open.
- OD-3 remains open.
- No artwork source has been approved yet.

## Licensing requirement

This decision does not weaken, replace, or bypass the repository's existing artwork licensing policy (`Documentation/RAIDIAN_WISE_REFERENCE_DATA_V1.md`, Section 5, "Image-Source Policy"). That policy remains in full effect and is restated here for clarity, not altered:

- The original 1909 Rider-Waite-Smith artwork is in the US public domain, but a specific modern scan, reprint, or colorization may carry its own separate copyright independent of the underlying 1909 work.
- Actual image assets must come from a verified public-domain source (a public-domain scan such as those hosted by Wikimedia Commons, or a similarly documented public-domain archive is given as an example, not a directive), not photographed or scanned from a copyrighted modern printed edition.
- File-level license/attribution verification must happen explicitly when a specific source is actually chosen — no source, specific file, or license has been verified, named, or approved by this decision or by any document to date.

## Next dependencies

1. **OD-2** — select and verify an appropriate artwork source (not resolved here).
2. **OD-3** — determine the asset-serving/bundling architecture (not resolved here; see `Documentation/CARD_IMAGE_ASSET_DESIGN.md` Section 6, Options A–D, for the previously-evaluated candidates).
3. Implement Spread Review artwork only after OD-2 and OD-3 are both resolved.
