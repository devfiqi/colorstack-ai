from collections.abc import Iterable

from colorstack_ai.playbooks.models import (
    DetectedPlaybook,
    EventType,
    PlaybookDefinition,
)


def _corpus(values: Iterable[str]) -> str:
    return " ".join(value.casefold() for value in values if value)


def detect_playbooks(
    *,
    event_name: str,
    aliases: list[str],
    state_text: list[str],
    fact_text: list[str],
    definitions: list[PlaybookDefinition],
) -> list[DetectedPlaybook]:
    names = _corpus([event_name, *aliases])
    context = _corpus([*state_text, *fact_text])
    candidates: list[DetectedPlaybook] = []
    overlay: DetectedPlaybook | None = None

    for definition in definitions:
        matched_name = [
            keyword
            for keyword in definition.detection_keywords
            if keyword.casefold() in names
        ]
        matched_context = [
            keyword
            for keyword in definition.detection_keywords
            if keyword.casefold() in context
        ]
        if not matched_name and not matched_context:
            continue
        confidence = 0.95 if matched_name else 0.75
        match = matched_name[0] if matched_name else matched_context[0]
        detected = DetectedPlaybook(
            key=definition.key,
            event_type=definition.event_type,
            reason=f"matched keyword {match!r}",
            confidence=confidence,
        )
        if definition.overlay:
            overlay = detected
        else:
            candidates.append(detected)

    sponsor_signals = ("sponsor", "funding", "company partner")
    if overlay is None and any(signal in context for signal in sponsor_signals):
        company = next(
            (
                definition
                for definition in definitions
                if definition.event_type == EventType.COMPANY_SPONSORED
                and definition.overlay
            ),
            None,
        )
        if company is not None:
            overlay = DetectedPlaybook(
                key=company.key,
                event_type=company.event_type,
                reason="current state contains sponsor-dependent evidence",
                confidence=0.85,
            )

    selected: list[DetectedPlaybook] = []
    if candidates:
        candidates.sort(key=lambda item: item.confidence, reverse=True)
        best = candidates[0]
        tied = [
            candidate
            for candidate in candidates
            if best.confidence - candidate.confidence < 0.1
        ]
        if len(tied) == 1:
            selected.append(best)
    if overlay is not None:
        selected.append(overlay)
    return selected
