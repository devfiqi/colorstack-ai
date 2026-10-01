from colorstack_ai.state.models import (
    ChangeType,
    CurrentValue,
    EntityType,
    FactEnvelope,
    PolicyDecision,
    StateField,
    StateProposal,
)


ACTIVE_STATUSES = {"open", "in_progress", "blocked"}
TERMINAL_STATUSES = {"completed", "cancelled"}


def _text_value(value: str, **extra: object) -> dict[str, object]:
    return {"text": value, **extra}


def _status_change_type(status: str) -> ChangeType:
    if status == "completed":
        return ChangeType.COMPLETION
    if status == "cancelled":
        return ChangeType.CANCELLATION
    return ChangeType.UPDATE


def _event_update_field(text: str) -> StateField | None:
    lowered = text.casefold()
    keyword_fields = (
        (("registration", "register", "rsvp"), StateField.REGISTRATION),
        (("food", "catering", "meal"), StateField.FOOD),
        (("judge", "speaker"), StateField.JUDGES_SPEAKERS),
        (("marketing", "promo", "flyer", "social media"), StateField.MARKETING),
        (("volunteer",), StateField.VOLUNTEERS),
        (("sponsor",), StateField.SPONSOR),
        (("funding", "budget", "money", "grant"), StateField.FUNDING_STATUS),
    )
    matches = {
        field
        for keywords, field in keyword_fields
        if any(keyword in lowered for keyword in keywords)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def proposals_for_fact(
    fact: FactEnvelope,
    entity_type: EntityType,
) -> list[StateProposal]:
    proposals: list[StateProposal] = []
    confidence = fact.confidence

    def add(
        field: StateField,
        value: dict[str, object],
        change_type: ChangeType,
        reason: str,
    ) -> None:
        proposals.append(
            StateProposal(
                entity_type=entity_type,
                field=field,
                value=value,
                change_type=change_type,
                reason=reason,
                reconciliation_confidence=confidence,
            )
        )

    if fact.fact_type in {"task", "commitment"} and entity_type == EntityType.TASK:
        status = fact.status or "open"
        add(
            StateField.STATUS,
            _text_value(status),
            _status_change_type(status),
            "task lifecycle fact",
        )

    if fact.owner_name or fact.owner_discord_id:
        add(
            StateField.OWNER,
            {
                "name": fact.owner_name,
                "discord_id": fact.owner_discord_id,
            },
            ChangeType.OWNERSHIP_CHANGE,
            "explicit owner information",
        )

    if fact.normalized_deadline or fact.deadline_text:
        deadline_payload: dict[str, object] = {
            "text": fact.deadline_text,
            "normalized": (
                fact.normalized_deadline.isoformat()
                if fact.normalized_deadline
                else None
            ),
            "exact": fact.normalized_deadline is not None,
        }
        field = (
            StateField.DEADLINE
            if entity_type == EntityType.TASK
            else StateField.EVENT_DATE_TIME
        )
        add(field, deadline_payload, ChangeType.UPDATE, "deadline information")

    if fact.fact_type == "location_change" and fact.value:
        add(
            StateField.LOCATION,
            _text_value(fact.value),
            ChangeType.CORRECTION,
            "location update",
        )
    elif fact.fact_type == "funding_update" and fact.value:
        add(
            StateField.FUNDING_STATUS,
            _text_value(fact.value),
            ChangeType.UPDATE,
            "funding update",
        )
    elif fact.fact_type == "sponsor_request" and fact.value:
        add(
            StateField.SPONSOR_REQUEST,
            _text_value(fact.value),
            ChangeType.UPDATE,
            "sponsor request",
        )
    elif fact.fact_type == "decision" and fact.value:
        add(
            StateField.DECISION,
            _text_value(fact.value),
            ChangeType.UPDATE,
            "recorded decision",
        )
    elif fact.fact_type == "blocker" and fact.value:
        add(
            StateField.BLOCKER,
            _text_value(fact.value),
            ChangeType.UPDATE,
            "reported blocker",
        )
        if entity_type == EntityType.TASK and not fact.status:
            add(
                StateField.STATUS,
                _text_value("blocked"),
                ChangeType.UPDATE,
                "blocker implies blocked task",
            )
    elif fact.fact_type == "open_question" and fact.value:
        add(
            StateField.OPEN_QUESTION,
            _text_value(fact.value),
            ChangeType.UPDATE,
            "open question",
        )
    elif fact.fact_type == "dependency" and fact.value:
        add(
            StateField.DEPENDENCY,
            _text_value(fact.value),
            ChangeType.UPDATE,
            "dependency update",
        )
    elif fact.fact_type == "event_update" and fact.value:
        field = _event_update_field(fact.value)
        if field is not None:
            add(
                field,
                _text_value(fact.value),
                ChangeType.UPDATE,
                "deterministic event-domain classification",
            )

    if fact.fact_type in {"status_change", "cancellation"} or (
        fact.status is not None
        and fact.fact_type not in {"task", "commitment"}
    ):
        status = fact.status
        if fact.fact_type == "cancellation":
            status = "cancelled"
        if status:
            change_type = _status_change_type(status)
            if status in ACTIVE_STATUSES and any(
                marker in fact.message_content.casefold()
                for marker in ("reopen", "resume", "back on", "restart")
            ):
                change_type = ChangeType.REOPEN
            add(
                StateField.STATUS,
                _text_value(status),
                change_type,
                "explicit status update",
            )

    return proposals


def evaluate_update(
    *,
    current: CurrentValue | None,
    proposal: StateProposal,
    fact: FactEnvelope,
) -> PolicyDecision:
    if current is None:
        return PolicyDecision(
            apply=True,
            outcome=ChangeType.NEW_INFO,
            reason="no current value",
        )

    if current.value == proposal.value:
        return PolicyDecision(
            apply=False,
            outcome=None,
            reason="value already current",
        )

    if fact.message_created_at < current.effective_at:
        return PolicyDecision(
            apply=False,
            outcome=ChangeType.CONTRADICTION,
            reason="older fact cannot replace newer state",
        )

    if current.evidence_kind == "explicit" and fact.evidence_kind != "explicit":
        return PolicyDecision(
            apply=False,
            outcome=ChangeType.CONTRADICTION,
            reason="inferred fact cannot replace explicit state",
        )

    if (
        current.evidence_kind == "inferred"
        and fact.evidence_kind == "inferred"
        and fact.confidence < current.confidence
    ):
        return PolicyDecision(
            apply=False,
            outcome=ChangeType.CONTRADICTION,
            reason="lower-confidence inference cannot replace current state",
        )

    if proposal.field in {StateField.DEADLINE, StateField.EVENT_DATE_TIME}:
        current_exact = bool(current.value.get("exact"))
        proposed_exact = bool(proposal.value.get("exact"))
        if current_exact and not proposed_exact:
            return PolicyDecision(
                apply=False,
                outcome=ChangeType.CONTRADICTION,
                reason="vague date cannot replace exact date",
            )

    if proposal.field == StateField.STATUS:
        old_status = current.value.get("text")
        new_status = proposal.value.get("text")
        if old_status in TERMINAL_STATUSES and new_status in ACTIVE_STATUSES:
            if (
                proposal.change_type != ChangeType.REOPEN
                or fact.evidence_kind != "explicit"
            ):
                return PolicyDecision(
                    apply=False,
                    outcome=ChangeType.CONTRADICTION,
                    reason="terminal state requires an explicit reopen",
                )
        if new_status == "completed":
            return PolicyDecision(
                apply=True,
                outcome=ChangeType.COMPLETION,
                reason="completion supersedes active task state",
            )
        if new_status == "cancelled":
            return PolicyDecision(
                apply=True,
                outcome=ChangeType.CANCELLATION,
                reason="explicit cancellation",
            )

    return PolicyDecision(
        apply=True,
        outcome=proposal.change_type,
        reason=proposal.reason,
    )
