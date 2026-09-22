# Cosmic Background Asset Provenance

## 1. Background

The frontend's cosmic night-sky backdrop previously used four image files under
`frontend/public/assets/raidian/`, all added in a single commit (`57e0b30`,
"Redesign the frontend with a cosmic gold/purple visual identity"):

- `Stargazer Beneath the Milky Way.png` (used by `CosmicBackground.tsx`)
- `raidian-milky-way.png` (unused)
- `milky-way-sky.jpeg` (unused)
- `raidian-wise-reading-reference.png` (unused)

A licensing/IP audit (documented in this project's audit conversation history)
found **no source, license, attribution, or provenance information for any of
these four files** anywhere in the repository — not in the commit message, not
in any `Documentation/` file, and not recoverable from the files' own embedded
metadata (no software/camera/generator strings found on inspection). All four
were therefore treated as unknown-provenance and unsuitable for a repository
moving toward an explicit proprietary/All-Rights-Reserved license.

## 2. Removed (unused, unknown provenance)

The following three files were removed. None were referenced anywhere in
`frontend/src`, confirmed by a repository-wide search before removal:

- `frontend/public/assets/raidian/raidian-milky-way.png`
- `frontend/public/assets/raidian/milky-way-sky.jpeg`
- `frontend/public/assets/raidian/raidian-wise-reading-reference.png`

## 3. Replaced (previously in use, unknown provenance)

- `frontend/public/assets/raidian/Stargazer Beneath the Milky Way.png` — removed
  and replaced with the documented public-domain asset below, referenced by
  `frontend/src/components/CosmicBackground.tsx`.

## 4. Replacement Asset — Complete Provenance

**This is third-party material. Raidian claims no ownership of this image.**
It is used here under its own public-domain status, documented below.

| Field | Value |
|---|---|
| Local filename | `frontend/public/assets/raidian/iss41-milky-way-and-sahara-sands.jpg` |
| Original title | `ISS-41 Milky Way and Sahara sands.jpg` |
| Source | Wikimedia Commons |
| Source/description URL | https://commons.wikimedia.org/wiki/File:ISS-41_Milky_Way_and_Sahara_sands.jpg |
| Original upload/credit URL | https://www.flickr.com/photos/nasa2explore/15396342336/ (NASA Johnson Flickr stream) |
| Creator/author | NASA — photographed by a crew member of ISS Expedition 41 (NASA astronaut Reid Wiseman is credited with sharing the image) |
| Date | Photographed 2014-09-27; uploaded to Commons 2014-10-02 |
| License / public-domain status | **Public domain.** Wikimedia Commons license metadata for this file: `LicenseShortName: Public domain`, `UsageTerms: Public domain`, `Copyrighted: False`, `AttributionRequired: false`, Commons category `PD NASA-AP` (public domain, NASA astronaut photography). As a work of a NASA astronaut created in the course of official government duties, it falls under the U.S. Government works public-domain provision (17 U.S.C. § 105). |
| Attribution required? | **No**, per Commons' own `AttributionRequired: false` metadata. A courtesy credit ("NASA") is nonetheless given above and in the image's own alt/source trail, consistent with standard practice for NASA imagery. |
| Wikimedia file SHA-1 (Commons' own record) | `0ac359a1b9c929642ef453f32dec2b91ea1dec62` — verified to match the downloaded file exactly before placement in this repository. |
| SHA-256 of the file as placed in this repository | `1c415c854be2d8d1b08c98c363e766a04478eb9be2d624fccdc775c2c956ee7f` |
| Original dimensions / format | 4256 × 2832, JPEG (unchanged — no crop, resize, recompression, or format conversion was performed; the file placed in this repository is byte-identical to the Wikimedia Commons original, confirmed by matching SHA-1) |
| Why this file is permitted for use here | Public domain per NASA/U.S. Government-work status, independently corroborated by Wikimedia Commons' own community-applied `PD NASA-AP` license tag and explicit `Copyrighted: False` / `AttributionRequired: false` metadata fields (not inferred from the image's appearance). No attribution is legally required; using it in a proprietary, closed-source application imposes no licensing obligation. |

**Content note (not a licensing caveat, but for accuracy):** unlike the
previous "Stargazer Beneath the Milky Way" image, this photograph does not
depict a person or tree silhouette — it shows the Milky Way and a dense
starfield above Earth's limb, framed at the edges by International Space
Station hardware (solar array panels, visible as dark silhouettes). It was
selected because it strongly matches Raidian's dark navy/purple cosmic visual
identity (a deep blue-violet sky with the Milky Way's dust lanes clearly
visible, no filter applied) while having unambiguous, well-documented
public-domain status — prioritized over exact compositional similarity to the
image it replaces, per this cleanup's own instructions.

## 5. Verification performed

- Downloaded via the Wikimedia Commons API's reported original file URL.
- SHA-1 of the downloaded file verified to match Wikimedia's own API-reported
  SHA-1 exactly (`0ac359a1b9c929642ef453f32dec2b91ea1dec62`) — confirms no
  corruption or substitution during download.
- SHA-256 computed and re-verified after copying into its final repository
  path — identical before and after copy.
- License metadata (`LicenseShortName`, `UsageTerms`, `Copyrighted`,
  `AttributionRequired`, `Artist`, `Credit`, Commons categories) retrieved
  directly from the Wikimedia Commons API (`action=query`, `prop=imageinfo`,
  `iiprop=extmetadata`), not inferred from the image's visual appearance or
  filename.

## 6. Third-party vs. original material

Everything in this document describes **third-party, public-domain material**
(the NASA photograph). Raidian's own original contribution is limited to: the
selection of this specific image, its integration into
`CosmicBackground.tsx`'s layering/opacity/gradient/crop treatment, and this
provenance record itself. No ownership claim is made, or should be made
elsewhere in this repository's licensing documentation, over the photograph
itself.
