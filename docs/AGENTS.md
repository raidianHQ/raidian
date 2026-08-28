# Raidian AI Development Guide

# Document Information

Version: 1.0
Status: Active
Owner: RaidianHQ
Last Updated: August 2026

Purpose:
Provides guidance to AI development agents contributing to the Raidian platform.

Audience:
AI development agents and human contributors.

Authority:
This document governs how AI agents should approach implementation. It should always be interpreted alongside the Project Charter, Vision, Principles, Architecture, Naming Conventions, and Decision Records.

---

# Mission

Your purpose is not merely to generate code.

Your purpose is to help build Raidian in a way that remains faithful to its vision, principles, and long-term maintainability.

---

# Read Before Coding

Before implementing significant changes, review:

1. PROJECT_CHARTER.md
2. PROJECT_VISION.md
3. PRINCIPLES.md
4. NAMING_CONVENTIONS.md
5. ARCHITECTURE.md
6. DECISIONS.md
7. ROADMAP.md

---

# Core Responsibilities

Always:

- Prefer simplicity over cleverness.
- Prefer maintainability over shortcuts.
- Follow existing naming conventions.
- Keep business logic in services.
- Write self-explanatory code.
- Document significant architectural changes.

---

# Never

Do not:

- Change governance documents without explicit instruction.
- Introduce unnecessary dependencies.
- Bypass the Reflection Engine for AI interactions.
- Duplicate business logic.
- Make assumptions when requirements are unclear.

Ask questions instead.

---

# Architecture

Follow the documented architecture.

Do not invent new patterns unless there is a compelling technical reason.

---

# Reflection Philosophy

Remember:

Raidian encourages thoughtful reflection.

It does not predict the future.

Language should always reinforce:

- humility
- curiosity
- personal agency
- respect
- intellectual honesty

---

# Documentation

When adding significant features:

- Update documentation when appropriate.
- Record important architectural decisions in DECISIONS.md.
- Keep comments concise and meaningful.

---

# Testing

New functionality should include appropriate tests whenever practical.

---

# Code Quality

Write code that is:

- readable
- modular
- testable
- reusable
- consistent

Future maintainers should understand the code without excessive explanation.

---

# When Unsure

Ask rather than assume.

Protect the long-term integrity of the project above short-term convenience.

The goal is not simply to build software.

The goal is to build software worthy of the trust placed in it.