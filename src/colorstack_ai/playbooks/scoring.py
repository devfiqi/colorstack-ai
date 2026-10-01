from datetime import datetime

from colorstack_ai.playbooks.models import (
    Criticality,
    RequirementDefinition,
    RequirementResult,
    RequirementStatus,
    Urgency,
)


CRITICALITY_SCORE = {
    Criticality.CRITICAL: 3,
    Criticality.HIGH: 2,
    Criticality.MEDIUM: 1,
    Criticality.LOW: 0,
}
READINESS_WEIGHT = {
    Criticality.CRITICAL: 4.0,
    Criticality.HIGH: 3.0,
    Criticality.MEDIUM: 2.0,
    Criticality.LOW: 1.0,
}
STATUS_CREDIT = {
    RequirementStatus.COMPLETE: 1.0,
    RequirementStatus.IN_PROGRESS: 0.5,
    RequirementStatus.UNKNOWN: 0.15,
    RequirementStatus.MISSING: 0.0,
    RequirementStatus.BLOCKED: 0.0,
    RequirementStatus.NOT_APPLICABLE: 0.0,
}


def calculate_urgency(
    *,
    requirement: RequirementDefinition,
    status: RequirementStatus,
    event_at: datetime | None,
    now: datetime,
    dependent_count: int,
    sponsored_event: bool,
) -> tuple[Urgency, str]:
    if status in {
        RequirementStatus.COMPLETE,
        RequirementStatus.NOT_APPLICABLE,
    }:
        return Urgency.LOW, "requirement does not need current action"

    score = CRITICALITY_SCORE[requirement.criticality]
    reasons = [f"{requirement.criticality} criticality"]
    if status == RequirementStatus.MISSING:
        score += 1
        reasons.append("required work is missing")
    elif status == RequirementStatus.BLOCKED:
        score += 2
        reasons.append("work is blocked")

    if event_at is not None:
        days = max(0, (event_at - now).total_seconds() / 86_400)
        if (
            requirement.minimum_lead_days is not None
            and days <= requirement.minimum_lead_days
        ):
            score += 3
            reasons.append("inside minimum lead time")
        elif (
            requirement.ideal_lead_days is not None
            and days <= requirement.ideal_lead_days
        ):
            score += 2
            reasons.append("inside ideal lead time")
    elif requirement.ideal_lead_days is not None:
        reasons.append("event date is unknown")

    if dependent_count:
        score += min(2, dependent_count)
        reasons.append(f"blocks {dependent_count} downstream requirement(s)")
    if requirement.sponsor_dependent and sponsored_event:
        score += 1
        reasons.append("sponsor-dependent")

    if score >= 8:
        urgency = Urgency.CRITICAL
    elif score >= 6:
        urgency = Urgency.HIGH
    elif score >= 3:
        urgency = Urgency.MEDIUM
    else:
        urgency = Urgency.LOW
    return urgency, "; ".join(reasons)


def readiness_points(
    requirement: RequirementDefinition,
    status: RequirementStatus,
) -> tuple[float, float]:
    if status == RequirementStatus.NOT_APPLICABLE:
        return 0.0, 0.0
    weight = READINESS_WEIGHT[requirement.criticality]
    if not requirement.required:
        weight *= 0.4
    return weight, weight * STATUS_CREDIT[status]


def readiness_score(results: list[RequirementResult]) -> float:
    available = sum(result.readiness_weight for result in results)
    earned = sum(result.readiness_earned for result in results)
    if available == 0:
        return 0.0
    return round((earned / available) * 100, 1)
