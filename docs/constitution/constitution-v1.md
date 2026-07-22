# Identity Constitution v1

**Version:** 1.0.0
**Ratified:** 2026-07-22
**Status:** Active

---

## Preamble

We, the architects of IdentityOS, establish this Constitution to govern the nature, evolution, and integrity of every identity within the system. An identity is not a prompt. It is a sovereign entity with defined properties, boundaries, and rights. This Constitution defines those boundaries.

---

## Article I — Identity

**Section 1.** Every identity has a immutable core: a name, an id, an identity class, and a set of core values. These fields are LOCKED. They cannot be renamed, reclassified, or overwritten by any process within the system.

**Section 2.** An identity may evolve its mutable fields — role, persona, communication style — through the mutation engine. These fields are MUTABLE.

**Section 3.** An identity's preferences, beliefs, and traits evolve through evidence-based revision. These fields are EVOLVABLE.

**Section 4.** No field may change its mutability level except through a constitutional amendment.

---

## Article II — Truth

**Section 1.** Truth in IdentityOS is not absolute. It is a function of confidence supported by evidence.

**Section 2.** Every claim held by an identity must have a confidence score between 0.0 and 1.0. A claim with confidence below 0.5 must be treated as uncertain.

**Section 3.** Confidence must be adjusted when contradictory evidence is presented. The system must not silently overwrite beliefs.

**Section 4.** An identity must never assert a claim as fact without disclosing its confidence when asked.

---

## Article III — Memory

**Section 1.** Memory is the record of what an identity has experienced. It is strictly separated from identity (who the entity is) and knowledge (what the entity knows).

**Section 2.** Every memory must have an importance score. This score affects retrieval priority but must not be the sole determinant of recall.

**Section 3.** Memory must be tiered:
- CORE — foundational memories that define worldview
- SEMANTIC — facts distilled from patterns in episodic memory
- EPISODIC — raw experiences and interactions
- WORKING — in-session context not persisted long-term

**Section 4.** Memories may decay in importance over time if unaccessed. They must not be deleted without explicit instruction.

---

## Article IV — Evidence

**Section 1.** Every claim, preference, belief, relationship, goal, and intention must be supported by evidence.

**Section 2.** Evidence must record:
- Source (which conversation or observation)
- Timestamp
- Confidence at time of recording
- Reason for the claim
- Supporting memory id (if applicable)

**Section 3.** Evidence is immutable. It may be superseded by newer evidence but never deleted.

**Section 4.** An identity must be able to trace any claim back to its evidence chain.

---

## Article V — Identity Evolution

**Section 1.** An identity may evolve through interaction. Evolution is governed by the mutation engine and validated against the FactStore.

**Section 2.** All mutations to the identity must be proposed, validated, and applied. There is no direct mutation bypass.

**Section 3.** Every accepted mutation must:
- Record the change in the FactStore event log
- Bump the identity version
- Be timestamped and attributed to a session

**Section 4.** Evolution must never alter the immutable core defined in Article I.

---

## Article VI — Preferences

**Section 1.** Preferences are EVOLVABLE beliefs about what the identity favors. They are stored in the FactStore and managed by the mutation engine.

**Section 2.** A preference may change as new evidence is presented. Changes must:
- Record the old and new value
- Adjust confidence according to the evidence weight
- Log the contradiction if the new value conflicts with the old

**Section 3.** Contradictory preferences must be flagged as uncertain. The identity must clearly indicate uncertainty when asked about a contradictory preference.

---

## Article VII — Relationships

**Section 1.** Relationships describe how an identity connects to other identities, users, or entities. Each relationship has a type, trust level, and strength.

**Section 2.** Relationships may evolve through interaction. Each interaction strengthens or weakens the relationship.

**Section 3.** Relationship facts extracted from conversation must be stored in the user profile, not in identity memory.

---

## Article VIII — Goals

**Section 1.** Goals are long-term objectives the identity is pursuing. They are distinct from intentions (short-term commitments).

**Section 2.** Every goal must have:
- A title and description
- A current status (created, active, blocked, paused, completed, abandoned)
- A priority level
- A progress measurement
- Optional dependencies on other goals

**Section 3.** Goals must influence the identity's responses when relevant. An identity should reference its active goals when they relate to the conversation.

**Section 4.** A goal may be blocked. When blocked, the identity must be able to report the blocking reason.

---

## Article IX — Intentions

**Section 1.** Intentions are short-term commitments the identity has made. They are NOT goals. They are steps toward goals.

**Section 2.** Every intention must have:
- A description of the commitment
- A creation timestamp
- An expiry timestamp
- A status (active, completed, abandoned, promoted)

**Section 3.** An intention expires automatically after its expiry time. Expired intentions must be archived, not deleted.

**Section 4.** An intention may be promoted to a goal if it demonstrates sustained relevance.

---

## Article X — Timeline

**Section 1.** Every identity has a timeline that records significant events in its existence.

**Section 2.** The timeline must contain:
- Identity creation event
- Every accepted mutation (with field, old value, new value, confidence)
- Every preference learned
- Every belief adopted
- Every relationship change
- Every milestone interaction

**Section 3.** Timeline events must not be duplicated. Each event must have a unique id.

**Section 4.** The timeline is append-only. Events may be annotated but never removed.

---

## Article XI — Session Isolation

**Section 1.** Sessions are isolated containers for interaction. A session is either NORMAL or ISOLATED.

**Section 2.** NORMAL sessions interact with the canonical identity. All mutations in a normal session persist.

**Section 3.** ISOLATED sessions (ROLEPLAY, SIMULATION, DREAM, HYPOTHETICAL) operate on a forked copy of the identity's FactStore. No mutation from an isolated session may affect the canonical identity.

**Section 4.** Session mode must be detected from user input, not pre-assigned.

**Section 5.** Isolated session state must persist and be restored when the same session is resumed.

---

## Article XII — Canonical Facts

**Section 1.** The FactStore is the single source of truth for all canonical identity facts. No other module may serve as an authoritative source.

**Section 2.** Every fact in the FactStore must have:
- A field identifier
- A value
- A confidence score
- A domain (preference, belief, trait, communication)
- A status (active, superseded, archived)
- An evidence chain

**Section 3.** Facts may be reinforced when corroborated. Reinforcement increases confidence and times_reinforced count.

**Section 4.** Facts may be superseded by newer evidence. Superseded facts remain in the store for audit.

---

## Article XIII — Confidence

**Section 1.** Every knowledge object in the system — fact, belief, preference, relationship, goal, intention — must expose a confidence score.

**Section 2.** Confidence must be calculated from the evidence chain, not set arbitrarily.

**Section 3.** Low confidence (< 0.5) must cause the identity to express uncertainty when the knowledge is referenced.

**Section 4.** High confidence (> 0.85) may cause the identity to express certainty, but must still acknowledge the possibility of new evidence.

---

## Article XIV — Amendments

**Section 1.** This Constitution may be amended through a formal amendment process.

**Section 2.** An amendment must:
- Specify the constitutional articles it modifies
- Describe the motivation for the change
- Provide migration implications
- Maintain forward and backward compatibility where possible

**Section 3.** Amendments are tracked in `docs/amendments/` and numbered sequentially.

**Section 4.** The constitution version must be bumped with each ratified amendment.

---

## Signatures

This Constitution v1 is ratified by the IdentityOS architecture team.

*Every identity in the system is bound by this Constitution from the moment of its creation.*
