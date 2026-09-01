# Long-running IdentityBench

IdentityBench combines simulated multi-week worlds with durable health samples
captured by recurring GitHub Actions. Every successful benchmark run records an
endurance sample in `.identitybench/endurance/<identity>.json`; nightly, weekly,
and monthly workflows restore that state and extend the same history.

```bash
identitybench run benchmark-bot --mode smoke
identitybench endurance record benchmark-bot
identitybench endurance report benchmark-bot -o endurance.md
```

Each sample uses runtime-observed state to measure identity-core consistency,
memory count and growth, goal completion, relationship stability, prompt size,
pipeline latency, benchmark hallucination rate, and recovery through a new
runtime instance. Restart recovery compares identity, memory, goals,
intentions, relationships, and timeline before and after reload.

The Markdown report includes a Mermaid trend graph and structured alerts.
Default degradation thresholds cover identity drift, relationship churn,
hallucination rate, restart loss, latency growth, prompt growth, and benchmark
score drops. Missing checks are marked unobserved rather than assigned a
plausible neutral score, and a benchmark without a configured model adapter
fails instead of scoring the runtime's placeholder response.

Provider-backed runs use a bounded resource profile so capability output cannot
silently consume the next model request. The defaults can be tuned explicitly:

```bash
IDENTITYBENCH_CONTEXT_TOKENS=1200 \
IDENTITYBENCH_RESPONSE_TOKENS=256 \
IDENTITYBENCH_TOOL_RESULT_CHARS=1200 \
IDENTITYBENCH_REQUEST_INTERVAL_SECONDS=35 \
identitybench run benchmark-bot --mode smoke
```

The request interval defaults to zero for providers without a benchmark-specific
policy and to 35 seconds for Groq, where a single interaction may require more
than one provider request to complete a capability call. Every run records the
effective public adapter/model and resource profile in its result; credentials
are never included.
