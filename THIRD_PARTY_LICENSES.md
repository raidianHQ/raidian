# Raidian Third-Party and Public-Domain Notices

## A. Overview

This file identifies material included in or used by Raidian that is
**not** claimed as Raidian-original proprietary material under
[LICENSE](LICENSE). It covers artwork assets, traditional reference
material, Scripture references, and third-party software dependencies. See
[COPYRIGHT.md](COPYRIGHT.md) for how these categories relate to Raidian's
own original material.

## B. Rider-Waite-Smith card artwork

Raidian's 78 tarot card images (`frontend/public/cards/rws/...`) are sourced
from Wikimedia Commons, from the `Category:Rider-Waite-Smith_tarot_deck_(TaionWC)`
collection (the "Pam-A" 1910 Rider (UK) trade-edition scan).

- **Public-domain basis (as documented by Wikimedia Commons):** a
  public-domain tag based on the death of the credited copyright holder,
  Arthur Edward Waite, in 1942 (life-plus-80-or-fewer jurisdictions), and a
  public-domain tag for US publication before January 1, 1931, plus the
  Creative Commons Public Domain Mark 1.0 applied by Commons itself.
- This determination is Wikimedia Commons' own community-applied license
  tag, not independent legal counsel obtained by this project.
- Full per-file provenance (source file, Commons description-page URL,
  SHA-256, dimensions, and acquisition methodology) for all 78 files is
  recorded in
  [Documentation/STEP74_ARTWORK_ASSET_ACQUISITION.md](Documentation/STEP74_ARTWORK_ASSET_ACQUISITION.md).

No additional licensing claims beyond what that document states are made
here.

## C. Cosmic background image

`frontend/public/assets/raidian/iss41-milky-way-and-sahara-sands.jpg`

Verified facts, drawn from
[Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md](Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md):

- **Description:** a NASA astronaut photograph taken during ISS Expedition
  41, depicting the Milky Way and starfield above Earth's limb.
- **Source:** Wikimedia Commons --
  https://commons.wikimedia.org/wiki/File:ISS-41_Milky_Way_and_Sahara_sands.jpg
- **Public-domain status:** public domain, per Wikimedia Commons' own
  license metadata for this file (`LicenseShortName: Public domain`,
  `UsageTerms: Public domain`, `Copyrighted: False`, Commons category
  `PD NASA-AP`), consistent with the U.S. Government works public-domain
  provision (17 U.S.C. § 105) for NASA astronaut photography.
- **Attribution requirement:** none, per the source's own
  `AttributionRequired: false` metadata.
- **SHA-256** (of the file as placed in this repository):
  `1c415c854be2d8d1b08c98c363e766a04478eb9be2d624fccdc775c2c956ee7f`

Raidian does not claim ownership of this image. See the provenance document
above for full verification methodology.

## D. Traditional tarot/reference material

Card names, the Major/Minor Arcana and suit structure, and traditional
tarot symbolism are longstanding traditional and factual material that
predates this project. Raidian does not claim this traditional
structure, naming, or symbolism as its own original expression.

This is distinct from -- and should not be confused with -- Raidian's own
original wording, organizational structure, synthesis, and software
implementation built around that traditional material, which is addressed
in [COPYRIGHT.md](COPYRIGHT.md) Section B.

## E. Scripture references

Raidian stores Scripture **references and metadata** -- book, chapter,
verse identifiers, and a translation label -- together with original
commentary written for the project (`context_note`,
`reflection_connection` in `backend/app/reference_data/scripture_references.yaml`).
It does not store or reproduce Bible passage text.

Approved translation labels, per
`backend/app/seed/loader.py` (`APPROVED_SCRIPTURE_TRANSLATIONS`), are
public-domain translations: **KJV**, **WEB**, and **ASV**. Of these, the
current seed dataset uses **KJV** citation labels only; WEB and ASV are
approved for use but not currently represented in the seed data.

Raidian does not claim copyright ownership over Scripture itself, over any
Bible translation, or over the translation labels used as citations.

## F. Software dependencies

This section reflects the direct dependencies declared in
`backend/pyproject.toml` and `frontend/package.json` as of this audit. It
is not represented as an exhaustive legal inventory of every transitive
dependency; it identifies the direct, declared dependencies plus the
notable transitive component in Section F.3 below.

The license of each dependency below governs that third-party component
only. It does not apply to, and has no bearing on, the license of
Raidian's own proprietary source code under [LICENSE](LICENSE). Each
dependency remains subject to its own license. Dependencies are
incorporated through their respective package-management mechanisms and
are not claimed as Raidian-original material.

### F.1 Backend (`backend/pyproject.toml`)

| Package | Version | License |
|---|---|---|
| FastAPI | 0.141.1 | MIT |
| Uvicorn | 0.52.4 | BSD-3-Clause |
| SQLAlchemy | 2.0.52 | MIT |
| Alembic | 1.19.1 | MIT |
| Pydantic | 2.13.4 | MIT |
| pydantic-settings | 2.15.0 | MIT |
| psycopg2-binary | 2.9.12 | LGPL with exception |
| python-dotenv | 1.2.3 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| pytest | 9.1.1 | MIT (development/test dependency only) |
| httpx2 | 2.13.0 | BSD-3-Clause |
| bcrypt | 5.0.0 | Apache-2.0 |
| PyJWT | 2.14.0 | MIT |

### F.2 Frontend (`frontend/package.json`)

| Package | License |
|---|---|
| React | MIT |
| React DOM | MIT |
| react-router-dom | MIT |
| Tailwind CSS | MIT |
| @tailwindcss/vite | MIT |
| Vite | MIT |
| TypeScript | Apache-2.0 |
| ESLint | MIT |
| typescript-eslint | MIT |
| eslint-plugin-react-hooks | MIT |
| eslint-plugin-react-refresh | MIT |
| @eslint/js | MIT |
| globals | MIT |
| @vitejs/plugin-react | MIT |
| @types/node, @types/react, @types/react-dom | MIT |

### F.3 Notable transitive dependency

- **lightningcss** and its platform binary (`lightningcss-win32-x64-msvc`),
  pulled in transitively via `@tailwindcss/vite`/Tailwind CSS's build
  tooling (confirmed present in `frontend/package-lock.json`) -- **MPL-2.0**.
  This is a build-time-only component (used by the Vite/Tailwind build
  pipeline, not bundled into or executed as part of Raidian's own
  distributed application code) and is used unmodified; MPL-2.0's own
  file-level terms remain applicable to that component. No claim is made
  here about MPL-2.0/proprietary-code compatibility beyond this factual
  description of how the component is used.

## G. Removed/unknown-provenance material

This repository previously contained several cosmic background image files
of unknown provenance (no source, license, or attribution information was
recoverable from the repository for any of them). They were removed during
this licensing/IP cleanup and are **not** current assets of this project:

- `Stargazer Beneath the Milky Way.png` (replaced by the NASA image
  documented in Section C above)
- `raidian-milky-way.png` (unused, removed)
- `milky-way-sky.jpeg` (unused, removed)
- `raidian-wise-reading-reference.png` (unused, removed)

See
[Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md](Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md)
for the historical record of this removal and replacement.

## H. No ownership claim over third-party material

Inclusion of any material in this repository does not mean Raidian claims
ownership of that material where it is identified in this document as
third-party or public-domain. Such material remains subject to its own
applicable license or public-domain status.
