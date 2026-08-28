# Raidian Architecture Decision Records (ADRs)

# Document Information

Version: 1.0
Status: Active
Owner: RaidianHQ
Last Updated: August 2026

Purpose:
Records significant architectural, engineering, governance, and product decisions that shape the Raidian platform. Each decision includes the reasoning behind it to preserve project knowledge and provide historical context for future contributors.

Audience:
Project owners, contributors, software engineers, AI development agents, and future maintainers.

Authority:
This document is the canonical historical record of approved project decisions. New architectural or governance decisions should be recorded here after acceptance.

---

# ADR-0001

## Title

Documentation-First Development

## Status

Accepted

## Date

August 27, 2026

## Decision

Raidian will establish governance, planning, and architectural documentation before significant implementation begins.

## Rationale

Clear documentation provides a shared understanding of the project's philosophy, architecture, and long-term direction. It enables consistent decision-making for both human contributors and AI development agents.

## Consequences

Implementation should reference the governance documents before introducing new features or architectural changes.

---

# ADR-0002

## Title

Reflection Over Prediction

## Status

Accepted

## Date

August 27, 2026

## Decision

Raidian will present symbolic interpretations as opportunities for thoughtful reflection rather than predictions of future events.

## Rationale

This approach aligns with the project's commitment to intellectual honesty, user agency, and respectful guidance.

## Consequences

All prompts, UI language, documentation, and AI behavior should reinforce this philosophy.

---

# ADR-0003

## Title

Platform Identity

## Status

Accepted

## Date

August 27, 2026

## Decision

Raidian is a guided reflection platform.

Tarot is the first reflective experience implemented within the platform rather than the platform's sole identity.

## Rationale

A broader platform identity provides room for future capabilities such as journaling, Scripture integration, dream reflection, and additional symbolic systems without requiring fundamental rebranding.

## Consequences

Architecture should remain modular and extensible.

---

# ADR-0004

## Title

Technology Stack

## Status

Accepted

## Date

August 27, 2026

## Decision

Raidian will use:

• React + Vite + TypeScript

• Tailwind CSS

• FastAPI

• SQLAlchemy

• Alembic

• Pydantic

• SQLite (development)

• PostgreSQL (production)

• GitHub Pages

• Render

## Rationale

The selected technologies provide a familiar, maintainable, and scalable foundation while allowing development effort to focus on product innovation rather than learning new frameworks.

## Consequences

Future technology changes should demonstrate substantial long-term benefit before replacing established components.

---

# ADR-0005

## Title

Reflection Engine Architecture

## Status

Accepted

## Date

August 27, 2026

## Decision

Artificial intelligence shall be accessed exclusively through the Reflection Engine.

Individual application components should never communicate directly with AI providers.

## Rationale

Centralizing AI interactions simplifies maintenance, improves consistency, enables provider independence, and ensures that all generated content follows the project's governance documents.

## Consequences

Future AI providers may be substituted without requiring widespread application changes.

---

# ADR-0006

## Title

Governance Hierarchy

## Status

Accepted

## Date

August 27, 2026

## Decision

Project governance follows the following order of authority:

1. Project Charter

2. Project Vision

3. Principles

4. Architecture

5. Decisions

6. Agents

7. Roadmap

8. Naming Conventions

## Rationale

A clearly defined governance hierarchy prevents ambiguity when documents appear to conflict.

## Consequences

Lower-level documents should never contradict higher-level governance without formal revision.