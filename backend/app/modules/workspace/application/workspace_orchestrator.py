"""WorkspaceOrchestrator — ClinicalContext → WorkspacePlan (pure, deterministic)."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from app.modules.workspace.application.context_hash import compute_context_hash
from app.modules.workspace.application.decision_engine import build_decision_queue
from app.modules.workspace.application.inputs import (
    OrchestratorInputs,
    ReviewAcknowledgements,
    SessionState,
)
from app.modules.workspace.application.layout_engine import (
    build_layout_drafts,
    build_pin_zone,
    to_directives,
)
from app.modules.workspace.application.priority_engine import compute_base_priorities
from app.modules.workspace.application.role_profiles import role_clamp
from app.modules.workspace.application.signals import extract_signals
from app.modules.workspace.application.state_machine import compute_workspace_state
from app.modules.workspace.application.story_engine import generate_story
from app.modules.workspace.domain.enums import (
    AttentionSlot,
    ClinicalObjectId,
    PriorityLevel,
    RoleProfile,
    SizeHint,
    SpecialtyLens,
)
from app.modules.workspace.domain.models import (
    CognitiveBudget,
    DecisionTrace,
    WorkspacePlan,
    WorkspacePlanMetadata,
)
from app.schemas.clinical_context import ClinicalContext


class WorkspaceOrchestrator:
    """
    Transforms immutable ClinicalContext into a derived WorkspacePlan.

    Does not mutate ClinicalContext. Does not perform clinical reasoning.
    Identical inputs → identical layout_directives, decision_queue, workspace_state
    (timestamps / compute_duration_ms excluded).
    """

    def compute(
        self,
        context: ClinicalContext,
        session_state: SessionState | None = None,
        lens: SpecialtyLens = SpecialtyLens.GENERAL_MEDICINE,
        role: RoleProfile = RoleProfile.DOCTOR,
        review_state: ReviewAcknowledgements | None = None,
        inputs: OrchestratorInputs | None = None,
        *,
        now: datetime | None = None,
        include_trace: bool = True,
    ) -> WorkspacePlan:
        started = time.perf_counter()
        session_state = session_state or SessionState()
        review_state = review_state or ReviewAcknowledgements()
        inputs = inputs or OrchestratorInputs()
        generated_at = now or datetime.now(timezone.utc)

        role_cfg = role_clamp(role)
        signals = extract_signals(context, session_state, inputs)
        priorities = compute_base_priorities(signals, role_cfg)

        story = generate_story(
            signals,
            role_cfg,
            review_state,
            priorities[ClinicalObjectId.STORY],
        )

        # Resolve contributes to ack-gate clearing (§6.3); acknowledged_objects
        # itself still means "explicit QueueItemAcknowledged only".
        effective_acknowledged = (
            review_state.acknowledged_objects | review_state.resolved_objects
        )

        drafts = build_layout_drafts(
            priorities,
            signals,
            role_cfg,
            effective_acknowledged,
            dismissed=review_state.dismissed_objects,
        )

        # Align story directive with generation outcome
        for draft in drafts:
            if draft.object_id is ClinicalObjectId.STORY:
                assessment = priorities[ClinicalObjectId.STORY]
                if story is None or assessment.hidden:
                    draft.slot = AttentionSlot.HIDDEN
                    draft.pinned = False
                    draft.size = SizeHint.COMPRESSED
                    draft.visibility_reason = assessment.visibility_reason
                    draft.priority = PriorityLevel.P3
                else:
                    draft.slot = AttentionSlot.SECONDARY
                    draft.pinned = False
                    draft.size = SizeHint.STANDARD
                    draft.visibility_reason = None
                    draft.priority = PriorityLevel.P2

        directives = to_directives(drafts)
        pin_zone = build_pin_zone(directives, signals, role_cfg)

        # Ensure pin_zone objects are actually pin+pinned (re-emit if needed)
        directive_map = {d.object_id: d for d in directives}
        fixed: list = []
        for d in directives:
            if d.object_id in pin_zone and (
                d.slot is not AttentionSlot.PIN or not d.pinned
            ):
                fixed.append(
                    d.model_copy(
                        update={
                            "slot": AttentionSlot.PIN,
                            "pinned": True,
                            "visibility_reason": None,
                        }
                    )
                )
            else:
                fixed.append(d)
        directives = tuple(fixed)

        # Drop pin_zone entries that somehow remain invalid
        pin_zone = tuple(
            oid
            for oid in pin_zone
            if oid in {d.object_id for d in directives}
            and directive_map.get(oid) is not None
        )
        # Recompute pin_zone from fixed directives
        pin_zone = build_pin_zone(directives, signals, role_cfg)
        # Final consistency pass
        final_dirs = []
        for d in directives:
            if d.object_id in pin_zone:
                final_dirs.append(
                    d.model_copy(
                        update={
                            "slot": AttentionSlot.PIN,
                            "pinned": True,
                            "visibility_reason": None,
                        }
                    )
                )
            else:
                final_dirs.append(d)
        directives = tuple(final_dirs)

        queue = build_decision_queue(
            directives,
            lens,
            role_cfg,
            effective_acknowledged,
            resolved=review_state.resolved_objects,
        )

        state = compute_workspace_state(
            signals,
            directives,
            queue,
            review_state,
            context_available=True,
        )

        primary_count = sum(
            1 for d in directives if d.slot is AttentionSlot.PRIMARY
        )
        expanded_count = sum(
            1
            for d in directives
            if d.size is SizeHint.EXPANDED and d.slot is not AttentionSlot.PIN
        )
        deferred_count = sum(
            1 for d in directives if d.slot is AttentionSlot.DEFERRED
        )

        trace_steps = []
        for assessment in priorities.values():
            trace_steps.extend(assessment.trace_steps)
        # Stable order
        trace_steps.sort(
            key=lambda s: (s.object_id.value, s.step_label, s.detail)
        )
        decision_trace = (
            DecisionTrace(steps=tuple(trace_steps)) if include_trace else None
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)

        return WorkspacePlan(
            session_id=context.session_id,
            workspace_state=state,
            layout_directives=directives,
            decision_queue=queue,
            story=story,
            pin_zone=pin_zone,
            cognitive_budget=CognitiveBudget(
                primary_count=primary_count,
                expanded_count=expanded_count,
                deferred_count=deferred_count,
            ),
            decision_trace=decision_trace,
            metadata=WorkspacePlanMetadata(
                context_hash=compute_context_hash(context),
                lens=lens,
                role=role,
                computed_at=generated_at,
                generated_at=generated_at,
                compute_duration_ms=elapsed_ms,
            ),
        )


workspace_orchestrator = WorkspaceOrchestrator()
