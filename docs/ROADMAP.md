# IdentityOS Roadmap

**Last updated:** 2026-07-22

---

## Current Status: Foundation Complete

IdentityOS **Architecture Foundation v1** is complete. The constitution, laws, amendment system, migration framework, goal engine, intention engine, evidence graph, and confidence system have all been implemented and verified.

**The architecture is now intentionally stable.**

Future architectural work should primarily arise from lessons learned while building real applications — not from inventing new abstractions in isolation.

---

## Phase 1: Architecture Foundation ✅ *COMPLETE*

| Milestone | Status |
|-----------|--------|
| Identity Constitution (14 articles) | ✅ |
| Identity Laws (10 domains) | ✅ |
| Amendment System | ✅ |
| Architecture Decision Records (7 ADRs) | ✅ |
| Migration Framework | ✅ |
| Evidence Graph | ✅ |
| Confidence System | ✅ |
| Goal Engine | ✅ |
| Intention Engine | ✅ |
| Memory Persistence | ✅ |

---

## Phase 2: Runtime Ecosystem 🔄 *ACTIVE*

**Theme:** Validate the runtime through real applications.

**Milestone:** [IdentityOS Runtime v2 — Real Agents](https://github.com/lacebx/IdentityOS/milestone/7)

### Application Layer

| Project | Priority | Status |
|---------|----------|--------|
| Identity Chat | High | 📋 Planned |
| Discord Agent | Medium | 📋 Planned |
| VSCode Extension | Medium | 📋 Planned |
| Browser Extension | High | 📋 Planned |

### Developer Infrastructure

| Project | Priority | Status |
|---------|----------|--------|
| IdentityOS SDK | High | 📋 Planned |
| Public REST API | High | 📋 Planned |
| Identity Debugger | High | 📋 Planned |
| Identity Replay | Medium | 📋 Planned |

### Validation

| Project | Priority | Status |
|---------|----------|--------|
| Long-running Benchmark | Medium | 📋 Planned |
| Developer Examples | Medium | 📋 Planned |

---

## Phase 3: Ecosystem Expansion 📋 *PLANNED*

- Open Identity Foundation governance
- Identity Marketplace
- Third-party runtime implementations
- Compliance test suite
- Multi-runtime interoperability

---

## Guiding Principles

### 1. Architecture Follows Application Experience

New architectural primitives should only be created when multiple applications independently demonstrate the same unmet need. No new subsystems without evidence from real usage.

### 2. Applications Before Abstractions

The first priority is building working applications. Architectural refinements are discovered, not designed.

### 3. Stability Enables Contribution

A stable architecture means contributors can build on IdentityOS without fear of breaking changes. The foundation is frozen. The ecosystem is open.

### 4. Quality Over Quantity

One well-built application is worth more than ten half-finished specifications. Each application should be polished before moving to the next.

---

## How to Contribute

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details on:

- Proposing new features
- Architecture decisions
- Constitutional amendments
- Code standards
- Testing expectations

## Full Issue List

All active work items are tracked in the [IdentityOS Runtime v2 Milestone](https://github.com/lacebx/IdentityOS/milestone/7).
