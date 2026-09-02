# Identity Chat

Identity Chat is the flagship web application bundled with IdentityOS. Start it
with `identity playground`, then open `http://localhost:8000/playground`.

The interface exposes conversation, session modes, identity evolution,
episodic and semantic memory, goals, expiring intentions, relationships,
timeline, constitution, debugger traces, replay, evaluation, and persistence.
Use the header to switch identities, change the current session mode, restart
the runtime, or download a portable JSON snapshot.

The chat endpoint uses newline-delimited JSON streaming. Runtime pipeline events
arrive while processing is underway. Adapters currently return a completed
model response to the runtime, so response text is transported in chunks after
that adapter call completes; the UI does not claim provider-level token
streaming when an adapter does not support it.

Goals and intentions can be created and completed from their panel controls.
Intentions auto-expire according to their persisted expiry time. NORMAL session
changes persist canonical facts; ROLEPLAY, SIMULATION, DREAM, and HYPOTHETICAL
sessions use the runtime's isolated session fact state.
