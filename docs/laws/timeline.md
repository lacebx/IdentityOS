# Timeline Law

**Domain:** Timeline
**Constitutional Basis:** Article X

---

## Purpose

Govern how identity events are recorded, organized, and queried. The timeline is the identity's life story.

## Responsibilities

- Record all significant identity events
- Prevent event duplication
- Support event querying by type and time range
- Provide narrative generation from events
- Persist timeline across sessions

## Allowed Mutations

| Operation | Allowed? | Conditions |
|-----------|----------|------------|
| Record event | Yes | Through interaction pipeline |
| Query events | Yes | Always |
| Annotate event | Yes | Additional metadata only |
| Delete event | No | Timeline is append-only |

## Conflict Resolution

- Event IDs must be unique — duplicate event recording is prevented
- Events are ordered by occurred_at timestamp
- An event may reference a previous event (e.g., "supersedes event X")

## Evidence Requirements

- Every event must have: event_type, title, description, significance (1-5)
- Events must have unique IDs
- Events must record their identity_id and session_id (if applicable)

## Event Types

| Type | Example |
|------|---------|
| creation | Identity created |
| milestone | Important interaction |
| preference_learned | Favorite color discovered |
| belief_adopted | New belief formed |
| trait_changed | Personality trait evolved |
| trust_changed | Relationship trust level changed |
| communication_changed | Style updated |
| intention_set | New intention formed |
| intention_completed | Intention fulfilled |
| goal_created | New goal added |
| goal_completed | Goal achieved |
| evidence_added | Evidence record created |

## Lifecycle

1. **Event occurs** — Interaction or system process triggers an event
2. **Recording** — Event is added to the timeline registry
3. **Querying** — Timeline may be queried for narrative generation
4. **Annotation** — Events may be annotated with additional context
5. **Archival** — Old events may be archived for performance

## Examples

```python
timeline.record_event(
    identity_id="lace",
    LifeEvent(
        event_type=LifeEventType.PREFERENCE_LEARNED,
        title="Learned preference: favorite color",
        description="User stated their favorite color is blue",
        significance=3,
        metadata={"field": "preferences.favorite_color", "value": "blue"},
    ),
)
```

## Future Extensions

- Timeline visualization
- Event pattern detection
- Timeline-based identity replay
- Cross-identity timeline comparison
