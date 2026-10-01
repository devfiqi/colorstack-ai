import json
from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from colorstack_ai.playbooks.detection import detect_playbooks
from colorstack_ai.playbooks.loader import PlaybookLoader
from colorstack_ai.playbooks.models import (
    EventSnapshot,
    EventType,
    PlaybookDefinition,
    ReadinessSummary,
    RequirementDefinition,
    RequirementEvidence,
    RequirementResult,
    RequirementStatus,
    StateEvidence,
)
from colorstack_ai.playbooks.repository import PlaybookRepository
from colorstack_ai.playbooks.scoring import (
    calculate_urgency,
    readiness_points,
    readiness_score,
)


class EventEvaluator:
    def __init__(
        self,
        *,
        repository: PlaybookRepository,
        loader: PlaybookLoader,
        now: datetime | None = None,
    ) -> None:
        self._repository = repository
        self._loader = loader
        self._now = now

    async def evaluate_event(self, event_id: UUID) -> ReadinessSummary:
        definitions = self._loader.load_all()
        playbook_ids = await self._repository.sync_definitions(definitions)
        snapshot = await self._repository.event_snapshot(event_id)
        if snapshot is None:
            raise ValueError(f"Event {event_id} was not found")

        state_text = [
            f"{field} {json.dumps(evidence.value, sort_keys=True)}"
            for field, evidence in snapshot.state.items()
        ]
        detected = detect_playbooks(
            event_name=snapshot.name,
            aliases=snapshot.aliases,
            state_text=state_text,
            fact_text=snapshot.fact_text,
            definitions=definitions,
        )
        await self._repository.assign_playbooks(
            event_id=event_id,
            detected=detected,
            ids=playbook_ids,
        )
        definitions_by_key = {
            definition.key: definition for definition in definitions
        }
        selected = [
            definitions_by_key[item.key]
            for item in detected
            if item.key in definitions_by_key
        ]

        results: list[RequirementResult] = []
        result_lookup: dict[str, RequirementResult] = {}
        definition_by_requirement: dict[
            str,
            tuple[PlaybookDefinition, str],
        ] = {}
        event_at = self._event_datetime(snapshot)
        now = self._now or datetime.now(UTC)
        sponsored = any(definition.overlay for definition in selected)

        for definition in selected:
            dependents = Counter(
                dependency
                for requirement in definition.requirements
                for dependency in requirement.dependencies
            )
            for requirement in definition.requirements:
                composite_key = f"{definition.key}:{requirement.key}"
                status, evidence, rationale, confidence = (
                    self._evaluate_requirement(snapshot, requirement)
                )
                urgency, urgency_reason = calculate_urgency(
                    requirement=requirement,
                    status=status,
                    event_at=event_at,
                    now=now,
                    dependent_count=dependents[requirement.key],
                    sponsored_event=sponsored,
                )
                weight, earned = readiness_points(requirement, status)
                result = RequirementResult(
                    requirement_key=composite_key,
                    requirement_name=requirement.name,
                    required=requirement.required,
                    criticality=requirement.criticality,
                    status=status,
                    urgency=urgency,
                    confidence=confidence,
                    evidence=evidence,
                    rationale=f"{rationale}; {urgency_reason}",
                    recommendation=(
                        None
                        if status
                        in {
                            RequirementStatus.COMPLETE,
                            RequirementStatus.NOT_APPLICABLE,
                        }
                        else requirement.next_step
                    ),
                    readiness_weight=weight,
                    readiness_earned=earned,
                )
                results.append(result)
                result_lookup[composite_key] = result
                definition_by_requirement[composite_key] = (
                    definition,
                    requirement.key,
                )

        for definition in selected:
            for requirement in definition.requirements:
                key = f"{definition.key}:{requirement.key}"
                result = result_lookup[key]
                if result.status in {
                    RequirementStatus.COMPLETE,
                    RequirementStatus.NOT_APPLICABLE,
                }:
                    continue
                blockers = [
                    result_lookup[f"{definition.key}:{dependency}"]
                    for dependency in requirement.dependencies
                    if result_lookup[f"{definition.key}:{dependency}"].status
                    in {
                        RequirementStatus.BLOCKED,
                    }
                ]
                if blockers:
                    result.status = RequirementStatus.BLOCKED
                    blocked_names = ", ".join(
                        blocker.requirement_name for blocker in blockers
                    )
                    result.rationale = (
                        f"Blocked by incomplete prerequisite(s): "
                        f"{blocked_names}; {result.rationale}"
                    )
                    urgency, reason = calculate_urgency(
                        requirement=requirement,
                        status=result.status,
                        event_at=event_at,
                        now=now,
                        dependent_count=0,
                        sponsored_event=sponsored,
                    )
                    result.urgency = urgency
                    result.rationale = f"{result.rationale}; {reason}"
                    weight, earned = readiness_points(
                        requirement,
                        result.status,
                    )
                    result.readiness_weight = weight
                    result.readiness_earned = earned

        counts = Counter(result.status for result in results)
        summary = ReadinessSummary(
            event_id=str(event_id),
            event_name=snapshot.name,
            event_types=(
                [item.event_type for item in detected]
                if detected
                else [EventType.UNKNOWN]
            ),
            readiness_score=readiness_score(results),
            complete=counts[RequirementStatus.COMPLETE],
            in_progress=counts[RequirementStatus.IN_PROGRESS],
            missing=counts[RequirementStatus.MISSING],
            blocked=counts[RequirementStatus.BLOCKED],
            unknown=counts[RequirementStatus.UNKNOWN],
            not_applicable=counts[RequirementStatus.NOT_APPLICABLE],
            critical_gaps=sum(
                1
                for result in results
                if result.criticality.value == "critical"
                and result.status
                in {
                    RequirementStatus.MISSING,
                    RequirementStatus.BLOCKED,
                }
            ),
            requirements=results,
        )
        await self._repository.save_evaluation(
            event_id=event_id,
            summary=summary,
            definition_by_requirement=definition_by_requirement,
        )
        return summary

    async def evaluate_all(self) -> list[ReadinessSummary]:
        summaries: list[ReadinessSummary] = []
        for event_id in await self._repository.active_event_ids():
            summaries.append(await self.evaluate_event(event_id))
        return summaries

    def _evaluate_requirement(
        self,
        snapshot: EventSnapshot,
        requirement: RequirementDefinition,
    ) -> tuple[
        RequirementStatus,
        list[RequirementEvidence],
        str,
        float,
    ]:
        evidence: list[RequirementEvidence] = []
        texts: list[str] = []
        matching_tasks = [
            task
            for task in snapshot.tasks
            if any(
                keyword.casefold() in task.title.casefold()
                for keyword in requirement.evaluation.task_keywords
            )
        ]

        for field in requirement.evaluation.event_fields:
            value = snapshot.state.get(field)
            if value is not None:
                evidence.append(self._event_evidence(value))
                texts.append(json.dumps(value.value).casefold())

        task_complete = False
        task_blocked = False
        for task in matching_tasks:
            for value in task.state.values():
                evidence.append(self._task_evidence(task.id, task.title, value))
                texts.append(json.dumps(value.value).casefold())
            status = task.state.get("status")
            status_text = status.value.get("text") if status else None
            task_complete = task_complete or status_text == "completed"
            task_blocked = task_blocked or status_text == "blocked"
            task_blocked = task_blocked or "blocker" in task.state

        combined = " ".join(texts)
        if any(
            marker in combined
            for marker in ("not applicable", "not needed", "no longer needed")
        ):
            return (
                RequirementStatus.NOT_APPLICABLE,
                evidence,
                "explicitly marked not applicable",
                self._confidence(evidence),
            )
        if task_blocked:
            return (
                RequirementStatus.BLOCKED,
                evidence,
                "matching task is explicitly blocked",
                self._confidence(evidence),
            )
        if task_complete:
            return (
                RequirementStatus.COMPLETE,
                evidence,
                "matching task is completed",
                self._confidence(evidence),
            )

        mode = requirement.evaluation.completion_mode
        if mode.value == "presence" and evidence:
            if (
                "event_date_time" in requirement.evaluation.event_fields
                and any(
                    item.value.get("exact") is False
                    for item in snapshot.state.values()
                    if item.field == "event_date_time"
                )
            ):
                return (
                    RequirementStatus.IN_PROGRESS,
                    evidence,
                    "date is present but not normalized exactly",
                    self._confidence(evidence),
                )
            return (
                RequirementStatus.COMPLETE,
                evidence,
                "required current-state evidence is present",
                self._confidence(evidence),
            )
        if mode.value == "terms" and evidence:
            terms = [
                term.casefold()
                for term in requirement.evaluation.completion_terms
            ]
            if terms and all(term in combined for term in terms):
                return (
                    RequirementStatus.COMPLETE,
                    evidence,
                    "all explicit completion terms are evidenced",
                    self._confidence(evidence),
                )
            return (
                RequirementStatus.IN_PROGRESS,
                evidence,
                "related work exists but completion criteria are not met",
                self._confidence(evidence),
            )
        if evidence or matching_tasks:
            return (
                RequirementStatus.IN_PROGRESS,
                evidence,
                "related work exists without completion evidence",
                self._confidence(evidence),
            )
        if requirement.required:
            return (
                RequirementStatus.MISSING,
                [],
                "required item has no source-linked evidence",
                1.0,
            )
        return (
            RequirementStatus.UNKNOWN,
            [],
            "optional item has no evidence or applicability decision",
            1.0,
        )

    @staticmethod
    def _event_datetime(snapshot: EventSnapshot) -> datetime | None:
        value = snapshot.state.get("event_date_time")
        if value is None:
            return None
        normalized = value.value.get("normalized")
        if not isinstance(normalized, str):
            return None
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    @staticmethod
    def _event_evidence(value: StateEvidence) -> RequirementEvidence:
        return RequirementEvidence(
            kind="event_state",
            description=f"event field {value.field}",
            source_fact_id=value.source_fact_id,
            source_message_id=value.source_message_id,
            state_field=value.field,
        )

    @staticmethod
    def _task_evidence(
        task_id: str,
        title: str,
        value: StateEvidence,
    ) -> RequirementEvidence:
        return RequirementEvidence(
            kind="task_state",
            description=f"{title}: {value.field}",
            source_fact_id=value.source_fact_id,
            source_message_id=value.source_message_id,
            state_field=value.field,
            task_id=task_id,
        )

    @staticmethod
    def _confidence(evidence: list[RequirementEvidence]) -> float:
        return 0.95 if evidence else 1.0
