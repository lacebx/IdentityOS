from __future__ import annotations

from core.identity import create_identity
from runtime.event_bus import EventBus, EventType
from runtime.orchestrator import IdentityRuntime, InteractionRequest


def test_event_bus_records_handler_failure_and_continues_delivery():
    bus = EventBus()
    delivered = []

    def broken_handler(event):
        raise RuntimeError("subscriber exploded")

    bus.subscribe(EventType.MESSAGE_RECEIVED, broken_handler)
    bus.subscribe(EventType.MESSAGE_RECEIVED, delivered.append)
    event = bus.emit(EventType.MESSAGE_RECEIVED, source="test", content="hello")

    assert delivered == [event]
    failures = bus.delivery_failures(event.id)
    assert failures == [{
        "event_id": event.id,
        "event_type": "message.received",
        "handler": "test_event_bus_records_handler_failure_and_continues_delivery.<locals>.broken_handler",
        "error_type": "RuntimeError",
        "error": "subscriber exploded",
        "timestamp": failures[0]["timestamp"],
    }]


def test_runtime_reports_stage_timings_and_completion_event():
    runtime = IdentityRuntime()
    identity = create_identity("Trace Bot", identity_id="trace-bot")
    runtime.register(identity)

    response = runtime.process(InteractionRequest(
        identity_id=identity.id,
        user_id="trace-user",
        user_input="Hello",
    ))

    timings = response.metadata["timings_ms"]
    assert response.metadata["capability_results"] == []
    assert timings["total"] >= 0
    for stage in (
        "identity_lookup",
        "session_resolution",
        "input_policy",
        "executive",
        "prometheus_pre",
        "context_composition",
        "model",
        "prometheus_post",
        "output_policy",
        "evaluation",
        "state_commit",
    ):
        assert timings[stage] >= 0
    completed = runtime.event_bus.history(EventType.INTERACTION_COMPLETED)
    assert completed[-1].payload["request_id"] == response.request_id
    assert completed[-1].payload["timings_ms"] == timings


def test_prometheus_budget_resets_for_each_interaction():
    runtime = IdentityRuntime()
    pipeline = runtime.prometheus.pipeline
    pipeline._interaction_acquisitions = 1
    pipeline._interaction_id = "old-request"

    runtime.prometheus.begin_interaction("new-request")
    assert pipeline._interaction_acquisitions == 0

    pipeline._interaction_acquisitions = 1
    runtime.prometheus.begin_interaction("new-request")
    assert pipeline._interaction_acquisitions == 1


def test_executive_recovery_runs_once_per_loaded_identity():
    class RecordingExecutive:
        def __init__(self):
            self.recovered = []

        def recover(self, identity_id):
            self.recovered.append(identity_id)

        def _ctx(self, identity_id, runtime=None):
            return None

        def render_state(self, identity_id):
            return ""

    runtime = IdentityRuntime()
    identity = create_identity("Recovery Bot", identity_id="recovery-bot")
    runtime.register(identity)
    executive = RecordingExecutive()
    runtime.executive = executive

    for index in range(2):
        runtime.process(InteractionRequest(
            identity_id=identity.id,
            user_id="recovery-user",
            user_input=f"Hello {index}",
        ))

    assert executive.recovered == [identity.id]
