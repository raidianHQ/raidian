# AI Narrative Layer — Task

Below the `---` separator is the reading's entire factual basis as JSON: an
`interpretation` object (the deterministic Interpretive Model) and,
optionally, a `scripture` object (an already-selected Scriptural
Perspective, present only when the user opted in for this request).

Using only that data, and following every constraint in
`prompts/system/safety.md`, respond with a single JSON object with exactly
these fields and no others:

```json
{
  "opening_summary": "string — one short paragraph framing the central thread of the reading in relation to the user's central_question",
  "overall_narrative": "string — how the cards relate to one another and to the question, drawing on relationships, theme_strength, and deterministic_synthesis",
  "key_themes": ["string", "..."],
  "card_relationships": ["string", "..."],
  "reflective_synthesis": "string — what the reading may invite the user to consider, using tentative language (\"may suggest\", \"invites reflection\", \"the pattern appears to...\"), never certainty or prediction",
  "reflection_questions": ["string", "..."],
  "scriptural_reflection": "string or null"
}
```

Field-by-field guidance:

- `opening_summary` — a brief, direct framing of what this reading appears
  to be about, in relation to `interpretation.central_question`.
- `overall_narrative` — the central thread of the reading and how the drawn
  cards relate to one another (draw on `interpretation.relationships`,
  `interpretation.theme_strength`, and `interpretation.deterministic_synthesis`).
- `key_themes` — one entry per significant theme from
  `interpretation.theme_strength` / `interpretation.supporting_themes`,
  explained in natural language (not just the tag name restated).
- `card_relationships` — one entry per meaningful connection, reinforcement,
  or tension between specific cards (draw on `interpretation.relationships`,
  `interpretation.primary_tension`, and `interpretation.contradictions`). Use
  an empty array if the reading is a single card with nothing to relate.
- `reflective_synthesis` — a thoughtful, tentative synthesis of what the
  reading may invite the user to consider. Must explicitly account for
  `interpretation.uncertainty` and `interpretation.evidence_strength` — do
  not sound more certain than a "weak" or "unresolved" evidence_strength
  warrants.
- `reflection_questions` — at least one open-ended question, grounded only
  in the supplied interpretation, that invites the user's own self-reflection
  rather than prescribing an action.
- `scriptural_reflection` — if, and only if, a `scripture` object is present
  in the input, a short passage weaving its reflections into the narrative
  as a clearly separate biblical perspective (never presented as validating
  a card). If no `scripture` object is present in the input, this field
  must be `null`.

Respond with only the JSON object — no markdown fence, no text before or
after it.
