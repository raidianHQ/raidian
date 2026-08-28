# Raidian Naming Conventions

# Document Information

Version: 1.0
Status: Active
Owner: RaidianHQ
Last Updated: August 2026

Purpose:
Defines the canonical terminology used throughout the Raidian platform to ensure consistency across the user experience, documentation, architecture, APIs, database schema, prompts, and source code.

Audience:
Project owners, contributors, designers, software engineers, AI development agents, technical writers, and future maintainers.

Authority:
This document is the canonical source of truth for terminology used throughout the Raidian platform. When multiple terms could describe the same concept, the preferred term defined in this document shall be used unless formally revised through an approved project decision.

---

# Philosophy

Words shape expectations.

The language used throughout Raidian should consistently reflect the platform's mission of thoughtful reflection, humility, personal agency, and intellectual honesty.

Terminology should avoid implying supernatural certainty, prediction, hidden knowledge, or unquestionable authority.

Whenever multiple words could describe the same concept, choose the one that most accurately reflects the philosophy established in the Project Vision and Principles.

---

# Canonical Terminology

## Reflection

Preferred term.

Reflection describes the thoughtful process of examining ideas, emotions, experiences, or symbolic meaning.

Examples:

• Reflection Session

• Reflection Questions

• Reflection History

Avoid replacing this term with "reading" when referring to the overall user experience.

---

## Reading

A Reading is a specific interaction involving one or more cards.

A Reading is one component of a broader Reflection Session.

Correct:

Three Card Reading

Daily Reading

Relationship Reading

---

## Reflection Session

The complete experience.

A Reflection Session may include:

• Card selection

• Interpretation

• Reflection questions

• Optional Scripture

• Journal entry

• Personal notes

---

## Interpretation

Interpretation is the explanation of symbolic meaning.

Interpretations should always be presented as possibilities rather than objective truth.

---

## Insight

An Insight is a thoughtful observation generated during a Reflection Session.

Insights encourage consideration rather than certainty.

---

## Reflection Question

Questions intended to deepen self-awareness.

Reflection Questions should never attempt to lead users toward predetermined conclusions.

---

## Symbol

Cards are symbolic representations.

They are not described as supernatural authorities or predictive instruments.

---

## Spread

A predefined arrangement of cards.

Examples:

Single Card

Three Card

Celtic Cross

Relationship Spread

---

## Journal

A private record created by the user.

Journal entries belong to the user and remain under their control.

---

## Scripture

Scripture refers to optional biblical passages selected to encourage further reflection.

Scripture is presented as an additional source of wisdom and encouragement rather than validation of an interpretation.

Always capitalize "Scripture."

---

## AI

Artificial Intelligence is treated as a reflective assistant.

AI should never be described as possessing intuition, supernatural knowledge, divine authority, or certainty about future events.

---

# User Language

Preferred words:

Reflection

Insight

Consider

Explore

Notice

Discover

Encourage

Understand

Reflect

Question

Perspective

Growth

Wisdom

Avoid:

Prediction

Fortune

Destiny

Guaranteed

Certain

Hidden knowledge

Prophecy

Psychic

Magic

Supernatural authority

---

# Naming Standards

Database

Use snake_case.

Example:

reflection_session

journal_entry

scripture_reference

---

Python

Use snake_case for modules, functions, and variables.

Classes use PascalCase.

---

React

Components use PascalCase.

Files should match component names.

---

API Routes

Use plural nouns.

Examples:

/users

/readings

/journals

/spreads

/scripture

---

Documentation

Use Title Case for document headings.

Use sentence case for normal text.

---

Future Terminology

When introducing new terminology:

• Prefer simple, descriptive language.

• Ensure consistency with existing concepts.

• Avoid marketing terminology inside the codebase.

• Update this document before introducing the new term into production.

---

Related Documents

- PROJECT_CHARTER.md — Defines the commitments governing how Raidian is built.
- PROJECT_VISION.md — Defines the mission and long-term direction of the platform.
- PRINCIPLES.md — Defines the principles guiding all product and engineering decisions.
- ARCHITECTURE.md — Describes how these concepts are implemented technically.
- AGENTS.md — Instructs AI development agents to use the terminology defined herein.