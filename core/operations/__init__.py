"""
core/operations — reusable autonomous-operator subsystem.

An operator identity (e.g. Aster) uses these primitives to run a persistent,
evidence-backed loop: observe a project, detect needs, discover and evaluate
opportunities, send permitted individualized outreach, monitor replies, follow
up, and escalate consequential decisions to a human.

Nothing in this package is specific to one mission.  Mission data lives in an
:class:`~core.operations.config.OperatorConfig`.
"""

from __future__ import annotations

from .capability_gap import CapabilityGap, CapabilityGapDetector, CapabilityStatus
from .composition import OutreachBrief, OutreachComposer
from .config import OperatorConfig
from .discovery import (
    Candidate,
    CallableCandidateSource,
    CandidateSource,
    OpportunityDiscoverer,
    SearchCandidateSource,
    StaticCandidateSource,
)
from .engine import OperationsEngine, TickReport
from .evaluation import ContactDecision, DuplicateContactPolicy, TargetEvaluator
from .followups import FollowUpPlanner
from .models import (
    BudgetState,
    ControlState,
    Evaluation,
    FollowUp,
    FollowUpStatus,
    Message,
    MessageDirection,
    MessageStatus,
    Need,
    NeedStatus,
    Opportunity,
    OpportunityStatus,
    ProjectState,
    ProvenanceEntry,
    ProvenancePhase,
    Relationship,
    RelationshipStatus,
)
from .monitor import (
    ConversationMonitor,
    InboundDisposition,
    InboundResult,
    classify_intent,
)
from .needs import NeedDetector, RequirementRule
from .observer import ProjectStateObserver
from .policy import Authority, AuthorityPolicy, AuthorizationDecision
from .presence import PresenceStatus, PresenceStore
from .store import OperationsStore

__all__ = [
    "PresenceStatus",
    "PresenceStore",
    "Authority",
    "AuthorityPolicy",
    "AuthorizationDecision",
    "BudgetState",
    "CallableCandidateSource",
    "Candidate",
    "CandidateSource",
    "CapabilityGap",
    "CapabilityGapDetector",
    "CapabilityStatus",
    "ContactDecision",
    "ControlState",
    "ConversationMonitor",
    "DuplicateContactPolicy",
    "Evaluation",
    "FollowUp",
    "FollowUpPlanner",
    "FollowUpStatus",
    "InboundDisposition",
    "InboundResult",
    "Message",
    "MessageDirection",
    "MessageStatus",
    "Need",
    "NeedDetector",
    "NeedStatus",
    "OperationsEngine",
    "OperationsStore",
    "OperatorConfig",
    "Opportunity",
    "OpportunityDiscoverer",
    "OpportunityStatus",
    "OutreachBrief",
    "OutreachComposer",
    "ProjectState",
    "ProjectStateObserver",
    "ProvenanceEntry",
    "ProvenancePhase",
    "Relationship",
    "RelationshipStatus",
    "RequirementRule",
    "SearchCandidateSource",
    "StaticCandidateSource",
    "TargetEvaluator",
    "TickReport",
    "classify_intent",
]
