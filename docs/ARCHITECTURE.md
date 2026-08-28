# Raidian Architecture

# Document Information

Version: 1.0
Status: Active
Owner: RaidianHQ
Last Updated: August 2026

Purpose:
Defines the technical architecture of the Raidian platform and the relationships between its major components.

Audience:
Project owners, contributors, software engineers, AI development agents, and future maintainers.

Authority:
This document is the canonical source for the platform's technical architecture. Architectural changes should be documented in DECISIONS.md before implementation.

---

# Architecture Philosophy

Raidian is designed as a modular platform for guided reflection. Each component has a single responsibility and communicates through well-defined interfaces.

---

# Technology Stack

Frontend:
- React
- Vite
- TypeScript
- Tailwind CSS

Backend:
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

Database:
- SQLite (Development)
- PostgreSQL (Production)

Hosting:
- GitHub Pages
- Render

---

# High-Level Architecture

User

↓

React Frontend

↓

FastAPI API

↓

Application Services

↓

Reflection Engine

↓

Database + AI Provider

---

# Core Services

- Authentication Service
- Reflection Engine
- Scripture Engine
- Journal Engine
- Growth Engine

Each service has a single responsibility.

---

# Design Principles

- Thin API layer
- Business logic in services
- AI isolated behind the Reflection Engine
- Database access through SQLAlchemy
- Modular, testable components
- Documentation before complexity

---

# Related Documents

- PROJECT_CHARTER.md
- PROJECT_VISION.md
- PRINCIPLES.md
- DECISIONS.md
- AGENTS.md