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
initially found no source, license, attribution, or provenance information for
any of these four files recorded anywhere in the repository, and treated all
four as unknown-provenance. On that basis, `Stargazer Beneath the Milky Way.png`
was temporarily removed from the active codebase and replaced as the active
cosmic background with a documented public-domain NASA photograph (Section 4
below).

**This was a mistake for `Stargazer Beneath the Milky Way.png` specifically.**
The Raidian project creator has confirmed that this is their own original
photograph, personally taken by them, with the enhanced/color-adjusted version
in this repository produced from that original photograph during Raidian's own
design work (the `57e0b30` cosmic redesign). It is Raidian-original material,
not third-party or unknown-provenance material, and this document has been
corrected accordingly. The image has been restored and `CosmicBackground.tsx`
again references it as the active cosmic background (Section 2 below); the
NASA photograph that temporarily replaced it is no longer the active
background (Section 4 below).

The audit's conclusion about the other three files -- unused, unknown
provenance, removed -- is unaffected by this correction and remains accurate
(Section 3 below).

## 2. Active background image -- Raidian-original photograph

**This is Raidian-original material. No third-party attribution is required.**

| Field | Value |
|---|---|
| Local filename | `frontend/public/assets/raidian/Stargazer Beneath the Milky Way.png` |
| Referenced by | `frontend/src/components/CosmicBackground.tsx` (active cosmic background) |
| Dimensions / format | 1672 x 941, PNG |
| Ownership | Original photograph personally taken by the Raidian project creator/user. The enhanced/color-adjusted version placed in this repository was produced from that original photograph during Raidian's own design work (the `57e0b30` cosmic redesign). |
| Subject | A tree silhouette and a stargazing figure beneath the Milky Way. |
| License / provenance status | Raidian-original material (see [COPYRIGHT.md](../COPYRIGHT.md) Section B). Not third-party, not public-domain-by-source, not unknown-provenance. No attribution to any outside source is required or appropriate. |
| History note | Removed from the active codebase during an earlier, mistaken unknown-provenance determination (commit `d1ca910`), and restored once that determination was corrected (see Section 1 above). Restored byte-identical from repository history (`57e0b30`). |

## 3. Removed (unused, unknown provenance)

The following three files were removed during the same cleanup and remain
removed -- this determination is unaffected by the Section 1 correction above.
None were referenced anywhere in `frontend/src`, confirmed by a
repository-wide search before removal, and no source, license, attribution,
or provenance information for any of them was recoverable from the
repository:

- `frontend/public/assets/raidian/raidian-milky-way.png`
- `frontend/public/assets/raidian/milky-way-sky.jpeg`
- `frontend/public/assets/raidian/raidian-wise-reading-reference.png`

## 4. Formerly-active replacement asset -- Complete Provenance (not currently active)

**Status: this image is no longer the active cosmic background.** It was used
as the active background between commit `d1ca910` and the correction described
in Section 1 above, while `Stargazer Beneath the Milky Way.png` was mistakenly
believed to be of unknown provenance. `CosmicBackground.tsx` now references
`Stargazer Beneath the Milky Way.png` again (Section 2). The file itself
remains present in the repository and this provenance record remains accurate
and is kept for reference, in case this or another public-domain image is
useful again in the future.

**This is third-party material. Raidian claims no ownership of this image.**
It is documented here under its own public-domain status, as verified below.

| Field | Value |
|---|---|
| Local filename | `frontend/public/assets/raidian/iss41-milky-way-and-sahara-sands.jpg` |
| Original title | `ISS-41 Milky Way and Sahara sands.jpg` |
| Source | Wikimedia Commons |
| Source/description URL | https://commons.wikimedia.org/wiki/File:ISS-41_Milky_Way_and_Sahara_sands.jpg |
| Original upload/credit URL | https://www.flickr.com/photos/nasa2explore/15396342336/ (NASA Johnson Flickr stream) |
| Creator/author | NASA -- photographed by a crew member of ISS Expedition 41 (NASA astronaut Reid Wiseman is credited with sharing the image) |
| Date | Photographed 2014-09-27; uploaded to Commons 2014-10-02 |
| License / public-domain status | **Public domain.** Wikimedia Commons license metadata for this file: `LicenseShortName: Public domain`, `UsageTerms: Public domain`, `Copyrighted: False`, `AttributionRequired: false`, Commons category `PD NASA-AP` (public domain, NASA astronaut photography). As a work of a NASA astronaut created in the course of official government duties, it falls under the U.S. Government works public-domain provision (17 U.S.C. § 105). |
| Attribution required? | **No**, per Commons' own `AttributionRequired: false` metadata. A courtesy credit ("NASA") is nonetheless given above and in the image's own alt/source trail, consistent with standard practice for NASA imagery. |
| Wikimedia file SHA-1 (Commons' own record) | `0ac359a1b9c929642ef453f32dec2b91ea1dec62` -- verified to match the downloaded file exactly before placement in this repository. |
| SHA-256 of the file as placed in this repository | `1c415c854be2d8d1b08c98c363e766a04478eb9be2d624fccdc775c2c956ee7f` |
| Original dimensions / format | 4256 x 2832, JPEG (unchanged -- no crop, resize, recompression, or format conversion was performed; the file placed in this repository is byte-identical to the Wikimedia Commons original, confirmed by matching SHA-1) |
| Why this file was permitted for use here | Public domain per NASA/U.S. Government-work status, independently corroborated by Wikimedia Commons' own community-applied `PD NASA-AP` license tag and explicit `Copyrighted: False` / `AttributionRequired: false` metadata fields (not inferred from the image's appearance). No attribution is legally required; using it in a proprietary, closed-source application imposes no licensing obligation. |

**Content note (not a licensing caveat, but for accuracy):** unlike
`Stargazer Beneath the Milky Way.png`, this photograph does not depict a
person or tree silhouette -- it shows the Milky Way and a dense starfield
above Earth's limb, framed at the edges by International Space Station
hardware (solar array panels, visible as dark silhouettes). It was selected,
while it was the active background, because it strongly matches Raidian's
dark navy/purple cosmic visual identity while having unambiguous,
well-documented public-domain status.

## 5. Verification performed (Section 4 image)

- Downloaded via the Wikimedia Commons API's reported original file URL.
- SHA-1 of the downloaded file verified to match Wikimedia's own API-reported
  SHA-1 exactly (`0ac359a1b9c929642ef453f32dec2b91ea1dec62`) -- confirms no
  corruption or substitution during download.
- SHA-256 computed and re-verified after copying into its final repository
  path -- identical before and after copy.
- License metadata (`LicenseShortName`, `UsageTerms`, `Copyrighted`,
  `AttributionRequired`, `Artist`, `Credit`, Commons categories) retrieved
  directly from the Wikimedia Commons API (`action=query`, `prop=imageinfo`,
  `iiprop=extmetadata`), not inferred from the image's visual appearance or
  filename.

## 6. Third-party vs. original material

- `Stargazer Beneath the Milky Way.png` (Section 2, currently active) is
  **Raidian-original material**: an original photograph taken by the Raidian
  project creator, enhanced/color-adjusted during Raidian's own design work.
  No third-party ownership claim applies to it, and none should be made
  elsewhere in this repository's licensing documentation.
- `iss41-milky-way-and-sahara-sands.jpg` (Section 4, not currently active) is
  **third-party, public-domain material** (the NASA photograph). Raidian's
  own original contribution regarding that file is limited to: the earlier
  selection of that specific image, its integration into
  `CosmicBackground.tsx`'s layering/opacity/gradient/crop treatment while it
  was active, and this provenance record. No ownership claim is made over
  that photograph itself.
