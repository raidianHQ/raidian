# Step 74 — Artwork Asset Acquisition & Validation

**Status:** Acquisition/validation only. No frontend source code, backend code, API contract, schema, migration, or `image_ref` value was changed. No rendering was implemented.

---

## 1. Purpose

Acquire and validate the physical artwork asset files for the 78-card Raidian Wise deck, per the three resolved open decisions (OD-1, OD-2, OD-3), place them under the frontend-bundled static location OD-3 selected, and document their provenance in full. Wiring these assets into any UI is explicitly out of scope for this step.

## 2. Selected Source

Wikimedia Commons, exactly as established by `Documentation/STEP72_OD2_ARTWORK_SOURCE_INVESTIGATION.md` — no substitute source, edition, or scan was used.

## 3. Source Collection/Category

`Category:Rider-Waite-Smith_tarot_deck_(TaionWC)` — re-queried live via the MediaWiki API this step (`action=query&list=categorymembers`), which returned exactly **78** file titles, confirming Step 72's finding independently and freshly rather than assuming it still held.

## 4. Edition/Print-Run

The "Pam-A" 1910 Rider (UK) trade-edition scan, as identified in Step 72.

## 5. Licensing Basis

Restated from Step 72, not weakened: sampled and (this step) fully-inventoried files carry (a) a public-domain tag based on the death of the credited copyright holder, Arthur Edward Waite, in 1942 (life-plus-80-or-fewer jurisdictions), and (b) a public-domain tag for US publication before January 1, 1931, plus the Creative Commons Public Domain Mark 1.0 applied by Commons itself. **This determination is Wikimedia Commons' own community-applied license tag, not independent legal counsel obtained by this project** — restating Step 72's caveat exactly, not glossed over.

## 6. Acquisition Date

2026-09-19 (this step). All source metadata (URLs, SHA1 hashes, dimensions, MIME types) was fetched live from the Wikimedia Commons API on this date, not reused from Step 72's earlier, smaller sample.

## 7. Total Expected Assets

78 (22 Major Arcana + 14 Wands + 14 Cups + 14 Swords + 14 Pentacles), derived from the authoritative card inventory re-extracted directly from `backend/app/reference_data/rider_waite_smith/*.yaml` this step (not assumed).

## 8. Total Acquired Assets

**78 of 78.** Every file in the TaionWC category was downloaded, and every one of Raidian Wise's 78 cards was matched to exactly one source file (a complete bijection — verified programmatically, no duplicate source usage, no unused source file, no unmapped card).

## 9. Source Filename Convention

Two patterns, both confirmed live via the API: Major Arcana as `RWS Tarot {2-digit rank} {Name}.jpg` (e.g. `RWS Tarot 00 Fool.jpg`); Minor Arcana as `{SuitPrefix}{2-digit position}.jpg` where `SuitPrefix` ∈ {`Wands`, `Cups`, `Swords`, `Pents`} and position 01–14 corresponds to Ace, Two, …, Ten, Page, Knight, Queen, King in that fixed order.

## 10. Application Filename Convention

Existing `image_ref` values were used as the authoritative logical path, with only the extension changed (`.png` → `.jpg`, see Section 15): `rws/major/00-the-fool.png` → `frontend/public/cards/rws/major/00-the-fool.jpg`; `rws/wands/four-of-wands.png` → `frontend/public/cards/rws/wands/four-of-wands.jpg`. This is a pure, mechanical, 1:1 derivation — no `image_ref` value itself was read, matched, or changed anywhere in the database or seed YAML.

## 11. Complete 78-Card Mapping

Deterministic and auditable — built programmatically from the actual YAML inventory and the actual Commons API response (never inferred from file-listing order alone: Major Arcana matched by the source filename's embedded rank number against `Card.rank`; Minor Arcana matched by suit name plus a fixed, explicit rank-to-position table). Verified: 78 cards mapped, 0 problems, 0 duplicate source usage, 0 unused source files, 78 unique final paths.

| Card | image_ref | Source file | Source page | Final application path | SHA-256 (final asset) |
|---|---|---|---|---|---|
| The Fool | `rws/major/00-the-fool.png` | `RWS Tarot 00 Fool.jpg` | [RWS Tarot 00 Fool.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_00_Fool.jpg) | `frontend/public/cards/rws/major/00-the-fool.jpg` | `557c6592b7310750…` |
| The Magician | `rws/major/01-the-magician.png` | `RWS Tarot 01 Magician.jpg` | [RWS Tarot 01 Magician.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_01_Magician.jpg) | `frontend/public/cards/rws/major/01-the-magician.jpg` | `e0569e468545abfd…` |
| The High Priestess | `rws/major/02-the-high-priestess.png` | `RWS Tarot 02 High Priestess.jpg` | [RWS Tarot 02 High Priestess.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_02_High_Priestess.jpg) | `frontend/public/cards/rws/major/02-the-high-priestess.jpg` | `0e87b5a22187a299…` |
| The Empress | `rws/major/03-the-empress.png` | `RWS Tarot 03 Empress.jpg` | [RWS Tarot 03 Empress.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_03_Empress.jpg) | `frontend/public/cards/rws/major/03-the-empress.jpg` | `2f0a9885c4f4e68b…` |
| The Emperor | `rws/major/04-the-emperor.png` | `RWS Tarot 04 Emperor.jpg` | [RWS Tarot 04 Emperor.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_04_Emperor.jpg) | `frontend/public/cards/rws/major/04-the-emperor.jpg` | `7a800b57c5b7da7b…` |
| The Hierophant | `rws/major/05-the-hierophant.png` | `RWS Tarot 05 Hierophant.jpg` | [RWS Tarot 05 Hierophant.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_05_Hierophant.jpg) | `frontend/public/cards/rws/major/05-the-hierophant.jpg` | `68faba7f016b2d76…` |
| The Lovers | `rws/major/06-the-lovers.png` | `RWS Tarot 06 Lovers.jpg` | [RWS Tarot 06 Lovers.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_06_Lovers.jpg) | `frontend/public/cards/rws/major/06-the-lovers.jpg` | `5a24e337a146568e…` |
| The Chariot | `rws/major/07-the-chariot.png` | `RWS Tarot 07 Chariot.jpg` | [RWS Tarot 07 Chariot.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_07_Chariot.jpg) | `frontend/public/cards/rws/major/07-the-chariot.jpg` | `3906e01a159d3b7f…` |
| Strength | `rws/major/08-strength.png` | `RWS Tarot 08 Strength.jpg` | [RWS Tarot 08 Strength.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_08_Strength.jpg) | `frontend/public/cards/rws/major/08-strength.jpg` | `b222f1799b8dc469…` |
| The Hermit | `rws/major/09-the-hermit.png` | `RWS Tarot 09 Hermit.jpg` | [RWS Tarot 09 Hermit.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_09_Hermit.jpg) | `frontend/public/cards/rws/major/09-the-hermit.jpg` | `0f86ac4560e598ce…` |
| Wheel of Fortune | `rws/major/10-wheel-of-fortune.png` | `RWS Tarot 10 Wheel of Fortune.jpg` | [RWS Tarot 10 Wheel of Fortune.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_10_Wheel_of_Fortune.jpg) | `frontend/public/cards/rws/major/10-wheel-of-fortune.jpg` | `2979bea7530572f4…` |
| Justice | `rws/major/11-justice.png` | `RWS Tarot 11 Justice.jpg` | [RWS Tarot 11 Justice.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_11_Justice.jpg) | `frontend/public/cards/rws/major/11-justice.jpg` | `028645f4ed40a820…` |
| The Hanged Man | `rws/major/12-the-hanged-man.png` | `RWS Tarot 12 Hanged Man.jpg` | [RWS Tarot 12 Hanged Man.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_12_Hanged_Man.jpg) | `frontend/public/cards/rws/major/12-the-hanged-man.jpg` | `0eacf7afe48e4b51…` |
| Death | `rws/major/13-death.png` | `RWS Tarot 13 Death.jpg` | [RWS Tarot 13 Death.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_13_Death.jpg) | `frontend/public/cards/rws/major/13-death.jpg` | `9e9cdd41a4d97569…` |
| Temperance | `rws/major/14-temperance.png` | `RWS Tarot 14 Temperance.jpg` | [RWS Tarot 14 Temperance.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_14_Temperance.jpg) | `frontend/public/cards/rws/major/14-temperance.jpg` | `a306b373f8ff1827…` |
| The Devil | `rws/major/15-the-devil.png` | `RWS Tarot 15 Devil.jpg` | [RWS Tarot 15 Devil.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_15_Devil.jpg) | `frontend/public/cards/rws/major/15-the-devil.jpg` | `f8e37102cbf21202…` |
| The Tower | `rws/major/16-the-tower.png` | `RWS Tarot 16 Tower.jpg` | [RWS Tarot 16 Tower.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_16_Tower.jpg) | `frontend/public/cards/rws/major/16-the-tower.jpg` | `ab5ce9bf29f32b9c…` |
| The Star | `rws/major/17-the-star.png` | `RWS Tarot 17 Star.jpg` | [RWS Tarot 17 Star.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_17_Star.jpg) | `frontend/public/cards/rws/major/17-the-star.jpg` | `20bb3e04c1655cc3…` |
| The Moon | `rws/major/18-the-moon.png` | `RWS Tarot 18 Moon.jpg` | [RWS Tarot 18 Moon.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_18_Moon.jpg) | `frontend/public/cards/rws/major/18-the-moon.jpg` | `866474dc3de02bf3…` |
| The Sun | `rws/major/19-the-sun.png` | `RWS Tarot 19 Sun.jpg` | [RWS Tarot 19 Sun.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_19_Sun.jpg) | `frontend/public/cards/rws/major/19-the-sun.jpg` | `6c21ef99fef3807b…` |
| Judgement | `rws/major/20-judgement.png` | `RWS Tarot 20 Judgement.jpg` | [RWS Tarot 20 Judgement.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_20_Judgement.jpg) | `frontend/public/cards/rws/major/20-judgement.jpg` | `1d670d30e6515540…` |
| The World | `rws/major/21-the-world.png` | `RWS Tarot 21 World.jpg` | [RWS Tarot 21 World.jpg](https://commons.wikimedia.org/wiki/File:RWS_Tarot_21_World.jpg) | `frontend/public/cards/rws/major/21-the-world.jpg` | `f866b87a3c4422f9…` |
| Ace of Wands | `rws/wands/ace-of-wands.png` | `Wands01.jpg` | [Wands01.jpg](https://commons.wikimedia.org/wiki/File:Wands01.jpg) | `frontend/public/cards/rws/wands/ace-of-wands.jpg` | `c29a4231878072d6…` |
| Two of Wands | `rws/wands/two-of-wands.png` | `Wands02.jpg` | [Wands02.jpg](https://commons.wikimedia.org/wiki/File:Wands02.jpg) | `frontend/public/cards/rws/wands/two-of-wands.jpg` | `b715689f6097b328…` |
| Three of Wands | `rws/wands/three-of-wands.png` | `Wands03.jpg` | [Wands03.jpg](https://commons.wikimedia.org/wiki/File:Wands03.jpg) | `frontend/public/cards/rws/wands/three-of-wands.jpg` | `1177316634bf3990…` |
| Four of Wands | `rws/wands/four-of-wands.png` | `Wands04.jpg` | [Wands04.jpg](https://commons.wikimedia.org/wiki/File:Wands04.jpg) | `frontend/public/cards/rws/wands/four-of-wands.jpg` | `9850a241100dd084…` |
| Five of Wands | `rws/wands/five-of-wands.png` | `Wands05.jpg` | [Wands05.jpg](https://commons.wikimedia.org/wiki/File:Wands05.jpg) | `frontend/public/cards/rws/wands/five-of-wands.jpg` | `6298f82e6ce5e752…` |
| Six of Wands | `rws/wands/six-of-wands.png` | `Wands06.jpg` | [Wands06.jpg](https://commons.wikimedia.org/wiki/File:Wands06.jpg) | `frontend/public/cards/rws/wands/six-of-wands.jpg` | `249a1eaa2de24dc9…` |
| Seven of Wands | `rws/wands/seven-of-wands.png` | `Wands07.jpg` | [Wands07.jpg](https://commons.wikimedia.org/wiki/File:Wands07.jpg) | `frontend/public/cards/rws/wands/seven-of-wands.jpg` | `0117736a1c9d5439…` |
| Eight of Wands | `rws/wands/eight-of-wands.png` | `Wands08.jpg` | [Wands08.jpg](https://commons.wikimedia.org/wiki/File:Wands08.jpg) | `frontend/public/cards/rws/wands/eight-of-wands.jpg` | `fbf01153074154c6…` |
| Nine of Wands | `rws/wands/nine-of-wands.png` | `Wands09.jpg` | [Wands09.jpg](https://commons.wikimedia.org/wiki/File:Wands09.jpg) | `frontend/public/cards/rws/wands/nine-of-wands.jpg` | `f0edfe460b1ba3fd…` |
| Ten of Wands | `rws/wands/ten-of-wands.png` | `Wands10.jpg` | [Wands10.jpg](https://commons.wikimedia.org/wiki/File:Wands10.jpg) | `frontend/public/cards/rws/wands/ten-of-wands.jpg` | `64c10fe7ba527498…` |
| Page of Wands | `rws/wands/page-of-wands.png` | `Wands11.jpg` | [Wands11.jpg](https://commons.wikimedia.org/wiki/File:Wands11.jpg) | `frontend/public/cards/rws/wands/page-of-wands.jpg` | `ecb79ab9035c43d3…` |
| Knight of Wands | `rws/wands/knight-of-wands.png` | `Wands12.jpg` | [Wands12.jpg](https://commons.wikimedia.org/wiki/File:Wands12.jpg) | `frontend/public/cards/rws/wands/knight-of-wands.jpg` | `00dd859cf067753c…` |
| Queen of Wands | `rws/wands/queen-of-wands.png` | `Wands13.jpg` | [Wands13.jpg](https://commons.wikimedia.org/wiki/File:Wands13.jpg) | `frontend/public/cards/rws/wands/queen-of-wands.jpg` | `f1646c86efe388df…` |
| King of Wands | `rws/wands/king-of-wands.png` | `Wands14.jpg` | [Wands14.jpg](https://commons.wikimedia.org/wiki/File:Wands14.jpg) | `frontend/public/cards/rws/wands/king-of-wands.jpg` | `671c7c53329fa99e…` |
| Ace of Cups | `rws/cups/ace-of-cups.png` | `Cups01.jpg` | [Cups01.jpg](https://commons.wikimedia.org/wiki/File:Cups01.jpg) | `frontend/public/cards/rws/cups/ace-of-cups.jpg` | `fd157290a61bd075…` |
| Two of Cups | `rws/cups/two-of-cups.png` | `Cups02.jpg` | [Cups02.jpg](https://commons.wikimedia.org/wiki/File:Cups02.jpg) | `frontend/public/cards/rws/cups/two-of-cups.jpg` | `5d1f09a9b69784e6…` |
| Three of Cups | `rws/cups/three-of-cups.png` | `Cups03.jpg` | [Cups03.jpg](https://commons.wikimedia.org/wiki/File:Cups03.jpg) | `frontend/public/cards/rws/cups/three-of-cups.jpg` | `25bfd4dbc2917a5a…` |
| Four of Cups | `rws/cups/four-of-cups.png` | `Cups04.jpg` | [Cups04.jpg](https://commons.wikimedia.org/wiki/File:Cups04.jpg) | `frontend/public/cards/rws/cups/four-of-cups.jpg` | `92097fe69d21dd0a…` |
| Five of Cups | `rws/cups/five-of-cups.png` | `Cups05.jpg` | [Cups05.jpg](https://commons.wikimedia.org/wiki/File:Cups05.jpg) | `frontend/public/cards/rws/cups/five-of-cups.jpg` | `07d2354d331f8a93…` |
| Six of Cups | `rws/cups/six-of-cups.png` | `Cups06.jpg` | [Cups06.jpg](https://commons.wikimedia.org/wiki/File:Cups06.jpg) | `frontend/public/cards/rws/cups/six-of-cups.jpg` | `bb6fb5b6de8c2281…` |
| Seven of Cups | `rws/cups/seven-of-cups.png` | `Cups07.jpg` | [Cups07.jpg](https://commons.wikimedia.org/wiki/File:Cups07.jpg) | `frontend/public/cards/rws/cups/seven-of-cups.jpg` | `3c9d1d310ca3f430…` |
| Eight of Cups | `rws/cups/eight-of-cups.png` | `Cups08.jpg` | [Cups08.jpg](https://commons.wikimedia.org/wiki/File:Cups08.jpg) | `frontend/public/cards/rws/cups/eight-of-cups.jpg` | `727c07c60753aa79…` |
| Nine of Cups | `rws/cups/nine-of-cups.png` | `Cups09.jpg` | [Cups09.jpg](https://commons.wikimedia.org/wiki/File:Cups09.jpg) | `frontend/public/cards/rws/cups/nine-of-cups.jpg` | `5d0704e0dc1de8ab…` |
| Ten of Cups | `rws/cups/ten-of-cups.png` | `Cups10.jpg` | [Cups10.jpg](https://commons.wikimedia.org/wiki/File:Cups10.jpg) | `frontend/public/cards/rws/cups/ten-of-cups.jpg` | `ac33d5a07ac63e10…` |
| Page of Cups | `rws/cups/page-of-cups.png` | `Cups11.jpg` | [Cups11.jpg](https://commons.wikimedia.org/wiki/File:Cups11.jpg) | `frontend/public/cards/rws/cups/page-of-cups.jpg` | `c6000e0ec6cf784e…` |
| Knight of Cups | `rws/cups/knight-of-cups.png` | `Cups12.jpg` | [Cups12.jpg](https://commons.wikimedia.org/wiki/File:Cups12.jpg) | `frontend/public/cards/rws/cups/knight-of-cups.jpg` | `99a7b7c91da744cb…` |
| Queen of Cups | `rws/cups/queen-of-cups.png` | `Cups13.jpg` | [Cups13.jpg](https://commons.wikimedia.org/wiki/File:Cups13.jpg) | `frontend/public/cards/rws/cups/queen-of-cups.jpg` | `a1732a137bfc441a…` |
| King of Cups | `rws/cups/king-of-cups.png` | `Cups14.jpg` | [Cups14.jpg](https://commons.wikimedia.org/wiki/File:Cups14.jpg) | `frontend/public/cards/rws/cups/king-of-cups.jpg` | `79ae249016aaafb0…` |
| Ace of Swords | `rws/swords/ace-of-swords.png` | `Swords01.jpg` | [Swords01.jpg](https://commons.wikimedia.org/wiki/File:Swords01.jpg) | `frontend/public/cards/rws/swords/ace-of-swords.jpg` | `32f0f932346a25b6…` |
| Two of Swords | `rws/swords/two-of-swords.png` | `Swords02.jpg` | [Swords02.jpg](https://commons.wikimedia.org/wiki/File:Swords02.jpg) | `frontend/public/cards/rws/swords/two-of-swords.jpg` | `a44b7e2b454db3dc…` |
| Three of Swords | `rws/swords/three-of-swords.png` | `Swords03.jpg` | [Swords03.jpg](https://commons.wikimedia.org/wiki/File:Swords03.jpg) | `frontend/public/cards/rws/swords/three-of-swords.jpg` | `4fdf7db3e7611561…` |
| Four of Swords | `rws/swords/four-of-swords.png` | `Swords04.jpg` | [Swords04.jpg](https://commons.wikimedia.org/wiki/File:Swords04.jpg) | `frontend/public/cards/rws/swords/four-of-swords.jpg` | `d4f9dad59b25daf3…` |
| Five of Swords | `rws/swords/five-of-swords.png` | `Swords05.jpg` | [Swords05.jpg](https://commons.wikimedia.org/wiki/File:Swords05.jpg) | `frontend/public/cards/rws/swords/five-of-swords.jpg` | `e4fc379d7ce3f767…` |
| Six of Swords | `rws/swords/six-of-swords.png` | `Swords06.jpg` | [Swords06.jpg](https://commons.wikimedia.org/wiki/File:Swords06.jpg) | `frontend/public/cards/rws/swords/six-of-swords.jpg` | `25279d7133301f59…` |
| Seven of Swords | `rws/swords/seven-of-swords.png` | `Swords07.jpg` | [Swords07.jpg](https://commons.wikimedia.org/wiki/File:Swords07.jpg) | `frontend/public/cards/rws/swords/seven-of-swords.jpg` | `6204a31b5949937c…` |
| Eight of Swords | `rws/swords/eight-of-swords.png` | `Swords08.jpg` | [Swords08.jpg](https://commons.wikimedia.org/wiki/File:Swords08.jpg) | `frontend/public/cards/rws/swords/eight-of-swords.jpg` | `019acbe3faff292c…` |
| Nine of Swords | `rws/swords/nine-of-swords.png` | `Swords09.jpg` | [Swords09.jpg](https://commons.wikimedia.org/wiki/File:Swords09.jpg) | `frontend/public/cards/rws/swords/nine-of-swords.jpg` | `b592a2ebe7fca2b6…` |
| Ten of Swords | `rws/swords/ten-of-swords.png` | `Swords10.jpg` | [Swords10.jpg](https://commons.wikimedia.org/wiki/File:Swords10.jpg) | `frontend/public/cards/rws/swords/ten-of-swords.jpg` | `10d0b161d115dc34…` |
| Page of Swords | `rws/swords/page-of-swords.png` | `Swords11.jpg` | [Swords11.jpg](https://commons.wikimedia.org/wiki/File:Swords11.jpg) | `frontend/public/cards/rws/swords/page-of-swords.jpg` | `ac69cec7c4b763fe…` |
| Knight of Swords | `rws/swords/knight-of-swords.png` | `Swords12.jpg` | [Swords12.jpg](https://commons.wikimedia.org/wiki/File:Swords12.jpg) | `frontend/public/cards/rws/swords/knight-of-swords.jpg` | `b38c1618eb6b5eca…` |
| Queen of Swords | `rws/swords/queen-of-swords.png` | `Swords13.jpg` | [Swords13.jpg](https://commons.wikimedia.org/wiki/File:Swords13.jpg) | `frontend/public/cards/rws/swords/queen-of-swords.jpg` | `55854543540d12f9…` |
| King of Swords | `rws/swords/king-of-swords.png` | `Swords14.jpg` | [Swords14.jpg](https://commons.wikimedia.org/wiki/File:Swords14.jpg) | `frontend/public/cards/rws/swords/king-of-swords.jpg` | `5307da08322c8ccf…` |
| Ace of Pentacles | `rws/pentacles/ace-of-pentacles.png` | `Pents01.jpg` | [Pents01.jpg](https://commons.wikimedia.org/wiki/File:Pents01.jpg) | `frontend/public/cards/rws/pentacles/ace-of-pentacles.jpg` | `fd6ddf90ead3062d…` |
| Two of Pentacles | `rws/pentacles/two-of-pentacles.png` | `Pents02.jpg` | [Pents02.jpg](https://commons.wikimedia.org/wiki/File:Pents02.jpg) | `frontend/public/cards/rws/pentacles/two-of-pentacles.jpg` | `1ee94470d0a0d53f…` |
| Three of Pentacles | `rws/pentacles/three-of-pentacles.png` | `Pents03.jpg` | [Pents03.jpg](https://commons.wikimedia.org/wiki/File:Pents03.jpg) | `frontend/public/cards/rws/pentacles/three-of-pentacles.jpg` | `a8d826b099c09203…` |
| Four of Pentacles | `rws/pentacles/four-of-pentacles.png` | `Pents04.jpg` | [Pents04.jpg](https://commons.wikimedia.org/wiki/File:Pents04.jpg) | `frontend/public/cards/rws/pentacles/four-of-pentacles.jpg` | `37e44050b8ac86dc…` |
| Five of Pentacles | `rws/pentacles/five-of-pentacles.png` | `Pents05.jpg` | [Pents05.jpg](https://commons.wikimedia.org/wiki/File:Pents05.jpg) | `frontend/public/cards/rws/pentacles/five-of-pentacles.jpg` | `5a6705ba00c102c9…` |
| Six of Pentacles | `rws/pentacles/six-of-pentacles.png` | `Pents06.jpg` | [Pents06.jpg](https://commons.wikimedia.org/wiki/File:Pents06.jpg) | `frontend/public/cards/rws/pentacles/six-of-pentacles.jpg` | `d9d67638f7f4075b…` |
| Seven of Pentacles | `rws/pentacles/seven-of-pentacles.png` | `Pents07.jpg` | [Pents07.jpg](https://commons.wikimedia.org/wiki/File:Pents07.jpg) | `frontend/public/cards/rws/pentacles/seven-of-pentacles.jpg` | `78a9d4965ce49719…` |
| Eight of Pentacles | `rws/pentacles/eight-of-pentacles.png` | `Pents08.jpg` | [Pents08.jpg](https://commons.wikimedia.org/wiki/File:Pents08.jpg) | `frontend/public/cards/rws/pentacles/eight-of-pentacles.jpg` | `13c82cbdec9ce101…` |
| Nine of Pentacles | `rws/pentacles/nine-of-pentacles.png` | `Pents09.jpg` | [Pents09.jpg](https://commons.wikimedia.org/wiki/File:Pents09.jpg) | `frontend/public/cards/rws/pentacles/nine-of-pentacles.jpg` | `e491630d7291a342…` |
| Ten of Pentacles | `rws/pentacles/ten-of-pentacles.png` | `Pents10.jpg` | [Pents10.jpg](https://commons.wikimedia.org/wiki/File:Pents10.jpg) | `frontend/public/cards/rws/pentacles/ten-of-pentacles.jpg` | `e14d5029ff2151a5…` |
| Page of Pentacles | `rws/pentacles/page-of-pentacles.png` | `Pents11.jpg` | [Pents11.jpg](https://commons.wikimedia.org/wiki/File:Pents11.jpg) | `frontend/public/cards/rws/pentacles/page-of-pentacles.jpg` | `d2c3cb2f6a602e62…` |
| Knight of Pentacles | `rws/pentacles/knight-of-pentacles.png` | `Pents12.jpg` | [Pents12.jpg](https://commons.wikimedia.org/wiki/File:Pents12.jpg) | `frontend/public/cards/rws/pentacles/knight-of-pentacles.jpg` | `6a652fbf447b7d0c…` |
| Queen of Pentacles | `rws/pentacles/queen-of-pentacles.png` | `Pents13.jpg` | [Pents13.jpg](https://commons.wikimedia.org/wiki/File:Pents13.jpg) | `frontend/public/cards/rws/pentacles/queen-of-pentacles.jpg` | `051a9a46a8069107…` |
| King of Pentacles | `rws/pentacles/king-of-pentacles.png` | `Pents14.jpg` | [Pents14.jpg](https://commons.wikimedia.org/wiki/File:Pents14.jpg) | `frontend/public/cards/rws/pentacles/king-of-pentacles.jpg` | `887b31bb3a9213e9…` |

*(SHA-256 values truncated to 16 hex characters for table readability; full 64-character hashes were computed for every file and cross-verified — see Section 13/19.)*

## 12. Source Identifiers/URLs

Every row above links to its Wikimedia Commons file description page (`descriptionurl` from the API's `imageinfo`), the authoritative page carrying that specific file's licensing statement. Direct binary URLs (`upload.wikimedia.org/...`) were used only for the download itself, not recorded here individually — the description-page links are the durable, human-checkable reference.

## 13. Final File Hashes

Every one of the 78 files placed under `frontend/public/` has a SHA-256 computed twice, independently: once immediately after download (before copying into the final location) and once again by reading the file back from its final `frontend/public/cards/...` path. **Both hashes matched for all 78 files, with zero mismatches** — confirming the copy step introduced no corruption. Full 64-character hashes are recorded in the acquisition working data; this document's table (Section 11) shows a 16-character prefix of each for readability.

## 14. Image Dimensions

All 78 images: height 1919–1920px, width 1090–1144px (natural per-card variation from scanning 78 individual physical cards — consistent, not anomalous). Aspect ratio ≈ 0.57–0.60, matching standard tarot card proportions (2.75″×4.75″ ≈ 0.579). Dimensions were verified **twice per file**: once from the Wikimedia API's own reported `width`/`height`, and independently again by parsing each downloaded file's actual JPEG SOF marker bytes with a pure-Python parser (no new dependency) — both methods agreed for all 78 files, with zero discrepancies.

## 15. File Formats

All 78 source files are JPEG (`image/jpeg`, confirmed via the Commons API's `mime` field for every file, and independently cross-checked with the system `file` utility on a sample, which additionally confirmed JFIF 1.01, baseline encoding, 1200 DPI scan density, 3-component/RGB color — no CMYK, grayscale, or corrupted files). **No format conversion was performed** — see Section 17 for the explicit reasoning.

## 16. File Sizes

Per-file: 702,301–1,198,823 bytes (≈686 KB – 1.17 MB), average ≈892 KB. Total added to the repository: **≈67 MB** across 78 files (`du -sh frontend/public/cards` reported 67M). This is the bounded, one-time size increase anticipated and explicitly accepted in `Documentation/STEP73_OD3_ARTWORK_ARCHITECTURE_DECISION.md` Section 5 (Option A evaluation) for a single, fixed 78-card deck.

## 17. Conversions Performed

**None. The original JPEG format was kept**, per the explicit evaluation this step was required to perform (not decided casually):
- **Visual fidelity:** JPEG is already lossy; converting to PNG would not recover any fidelity, and re-encoding through an additional lossless wrapper provides no visible benefit for content that is already photographically/lithographically continuous-tone.
- **File size:** PNG (lossless) would substantially inflate each file — likely several times larger for this kind of scanned, textured artwork — multiplying the ≈67 MB repository addition for zero quality gain.
- **Browser compatibility:** JPEG has universal browser support; no concern either way.
- **Git repository size:** Directly follows from the file-size point — keeping JPEG keeps the one-time repository growth bounded and reasonable.
- **Deterministic reproducibility:** Keeping the exact downloaded bytes (verified against Wikimedia's own reported SHA1, Section 13) is maximally reproducible and auditable forever; a conversion step would itself need to be documented and would be a new source of "is this really derived correctly from the original" uncertainty.
- **Does `image_ref`'s `.png` convention require PNG content?** No — confirmed across Steps 48–73 that `image_ref` is a free-form placeholder string, validated only for non-emptiness, never parsed or enforced against actual file content by any code. The `.png` suffix is Raidian Wise's own pre-existing naming convention, not a content-type contract.

## 18. Naming Normalization Performed

Final application filenames were derived mechanically from each card's existing `image_ref` value with only the file extension changed (`.png` → `.jpg`); no other renaming, slugging, or reformatting was applied. This is intentional and documented — see Section 10.

## 19. Verification Methodology

Performed for **all 78 files**, not a sample (sampling was reserved for visual inspection only, Section 21):
1. Re-extracted the authoritative 78-card inventory directly from `backend/app/reference_data/rider_waite_smith/*.yaml` (not assumed from prior steps).
2. Queried the Commons category live via the MediaWiki API — confirmed exactly 78 members.
3. Built a deterministic card→source-file mapping using actual card identity (rank/suit) against actual source filename structure — not inferred from listing order.
4. Verified the mapping was a complete bijection: 78 cards mapped, 0 problems, 0 duplicate source usage, 0 unused source files.
5. Downloaded all 78 files (with rate-limit backoff/retry as Wikimedia's servers required) and verified each one's SHA-1 and byte size against the Commons API's own reported values at download time — **all 78 matched exactly**.
6. Computed SHA-256 for every downloaded file; confirmed **78 unique hashes, zero duplicates** (no accidental identical-content downloads).
7. Independently re-parsed every file's actual JPEG dimensions from its bytes and cross-checked against the API-reported dimensions — **zero discrepancies**.
8. Copied all 78 files into their final `frontend/public/cards/...` locations; re-hashed every placed file and confirmed it matched its pre-copy hash exactly — **zero corruption**.
9. Counted final files per category: 22 Major Arcana, 14 Wands, 14 Cups, 14 Swords, 14 Pentacles — **exact match to the expected inventory**.
10. Confirmed 78 unique final file paths (no path collisions).

## 20. Missing/Duplicate Asset Checks

- **Missing:** none — every one of the 78 expected `image_ref` values has a corresponding placed file, confirmed by direct existence check.
- **Duplicate:** none — 78 unique SHA-256 hashes among 78 files; 78 unique final paths.
- **Extra/unrelated:** none — every downloaded file traces to exactly one expected card via the deterministic mapping; no stray files were introduced.

## 21. Licensing/Provenance Caveats

Restated, not weakened, from Step 72:
- Wikimedia Commons' public-domain determination is a **community-applied license tag**, not independent legal counsel obtained by this project.
- This step establishes file-level provenance (exact source file, exact description page, exact hash) for all 78 files — a materially stronger record than a category-level blanket statement — but does not convert that into a formal legal opinion.
- The ultimate scan's own chain of custody (the file pages cite `muzendo.jp/blog/` as a contributing source, per Step 72) remains a blog, not an archival institution; this affects confidence in scan *provenance/quality*, not the underlying public-domain legal basis, which rests on the Waite-death/pre-1931-US-publication facts independent of who scanned it.

## 22. Implementation Status

**Not implemented.** No frontend source file was changed. `SpreadReviewPage.tsx` and `CardEntryPage.tsx` still render text/tile placeholders exactly as before this step. Rendering these assets is explicitly deferred to a future step.

## 23. Git Status

See the Step 74 final report for the exact `git status` output captured after this document was written.
