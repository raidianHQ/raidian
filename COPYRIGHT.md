# Raidian Copyright and Ownership Notice

## A. Purpose

This document identifies the categories of material that Raidian treats as
original project material, reserved under [LICENSE](LICENSE), and
distinguishes those categories from third-party and public-domain material
included in or used by this repository. It is a project documentation
statement intended to make Raidian's ownership posture explicit and
conservative, not an exhaustive legal inventory.

## B. Raidian-original material

Based on the actual contents of this repository, Raidian treats the
following as original project material:

- the backend application source code and architecture (`backend/`),
  including its API layer, data models, and Alembic migrations;
- the frontend application source code and implementation (`frontend/src`),
  including its component structure and visual/interaction design as
  expressed in code;
- original project documentation, design documents, and governance
  documents (`Documentation/`), including product specifications,
  architectural decision records, and step-by-step design/audit records;
- the interpretation-engine implementation (`backend/app/services/interpretation/`)
  -- the code that computes a reading's structural themes -- as distinct
  from the traditional tarot facts it operates on (see Section C);
- the narrative-assembly and orchestration implementation
  (`backend/app/services/narrative/`, `backend/app/services/ai_narrative/`
  and related modules);
- original prompts and prompt architecture used to instruct the AI
  narrative layer;
- original commentary written for the project, including the
  `context_note` and `reflection_connection` fields in
  `backend/app/reference_data/scripture_references.yaml` (original
  commentary connecting a theme to a Scripture reference -- never the
  underlying Scripture passage text itself, which is not stored in this
  repository; see Section C);
- original theme taxonomy and organizational structures created for the
  project (for example, `theme_vocabulary.yaml`'s tag set), to the extent
  they reflect original selection and arrangement rather than
  traditionally-given facts;
- original card-meaning wording and other original expressive content
  authored for the project's reference data, to the extent copyrightable,
  as distinct from the traditional card names, structure, and symbolism
  those meanings describe (see Section C); and
- original astrology/correspondence notes and organizational structure
  authored by the project, to the extent copyrightable, as distinct from
  the underlying traditional correspondence facts themselves (see Section D
  for important caveats specific to this category); and
- the active cosmic background photograph
  (`frontend/public/assets/raidian/Stargazer Beneath the Milky Way.png`) --
  an original photograph personally taken by the Raidian project
  creator/user, with the enhanced/color-adjusted version in this repository
  produced from that original photograph during Raidian's own design work;
  see
  [Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md](Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md).

### AI-assisted material

Some material in this repository was created with AI assistance and
reviewed and adopted by the project owner. The copyright treatment of
AI-assisted material is not settled by simple rule: it depends on
applicable law and on the extent of human creative authorship --
selection, arrangement, editing, and adoption -- actually exercised over
the resulting material. This document does not claim that all AI-assisted
content is automatically copyrighted by Raidian, and it does not claim that
AI-assisted content is automatically public domain. Raidian claims its
human-authored contributions to such material -- including selection,
editing, structuring, and adoption -- to the extent those contributions are
protected by applicable law.

## C. Material not claimed as Raidian-owned

The following categories of material appear in or are used by this
repository but are **not** claimed as Raidian-owned:

- **a formerly-used cosmic background photograph**
  (`iss41-milky-way-and-sahara-sands.jpg`) -- a public-domain NASA astronaut
  photograph, present in the repository but not the currently active cosmic
  background (the active one is Raidian-original material; see Section B);
  see
  [Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md](Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md);
- **the Rider-Waite-Smith card artwork** -- sourced from Wikimedia Commons
  and documented as public domain there; see
  [Documentation/STEP74_ARTWORK_ASSET_ACQUISITION.md](Documentation/STEP74_ARTWORK_ASSET_ACQUISITION.md);
- **traditional tarot structure, names, and symbolism** (the Major/Minor
  Arcana structure, suit names, traditional card meanings as a body of
  cultural knowledge, and similar factual/traditional material), which
  predate this project and are not proprietary to it;
- **Scripture citations and references** (book, chapter, and verse
  identifiers, and translation labels), which are not authored by this
  project; and
- **third-party software dependencies**, each governed by its own license.

For each of these, see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) and the provenance
documentation referenced above and there.

## D. Correspondence data

This section requires particular care because of an unresolved provenance
question identified during this project's licensing/IP audit.

A source spreadsheet, `Documentation/Source_Data/RaidianWiseDeckTemplate_Jenn.xlsm`,
was previously present in this repository. Based on what the repository
audit could establish:

- the source spreadsheet was previously present in the repository;
- it has since been removed from the current working tree/repository
  state;
- derived correspondence data remains in the project (for example,
  `backend/app/reference_data/rider_waite_smith/correspondences.yaml`);
- project documentation describes this derived data as structured
  correspondence information; and
- the provenance and ownership status of the original spreadsheet, and any
  rights associated with it, were **not established** by the repository
  audit.

Raidian does not claim ownership of the original spreadsheet, and does not
claim that permission to use or redistribute it was obtained. For the
derived correspondence data that remains in the project, a distinction
should be maintained between (a) factual/traditional astrological or
correspondence information, which is not claimed as Raidian-owned, and
(b) any original expressive notes, wording, or organizational structure
that Raidian itself authored around that factual information, which is
treated the same as other Raidian-original material under Section B. No
blanket ownership claim is made over the underlying third-party facts.

## E. Artwork

Provenance and licensing information for artwork assets used by Raidian is
documented in:

- [Documentation/STEP74_ARTWORK_ASSET_ACQUISITION.md](Documentation/STEP74_ARTWORK_ASSET_ACQUISITION.md)
  (Rider-Waite-Smith card artwork), and
- [Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md](Documentation/COSMIC_BACKGROUND_ASSET_PROVENANCE.md)
  (cosmic background photographs).

Raidian does not claim ownership of the Rider-Waite-Smith card artwork
(public domain) or of the formerly-used NASA cosmic background photograph
(public domain, not currently active; see Section C). The currently active
cosmic background photograph is Raidian-original material (see Section B).
These documents govern the provenance record for those assets; this
section only cross-references them.

## F. Reservation of rights

Raidian-original material as described in Section B remains reserved under
[LICENSE](LICENSE), subject to applicable law and the exclusions described
in Sections C and D of this document.

## G. Legal caution

This document is a project documentation statement prepared for Raidian's
own internal clarity. It is **not legal advice**. Formal legal questions --
including, without limitation, the copyrightability of AI-assisted
material, the status of the correspondence data described in Section D, or
the scope of any third-party license -- should be reviewed by qualified
legal counsel before being relied upon for any legal purpose.
