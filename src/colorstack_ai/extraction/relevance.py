import re
from dataclasses import dataclass

from colorstack_ai.extraction.models import ExtractionContext


@dataclass(frozen=True)
class RelevanceDecision:
    is_relevant: bool
    reasons: tuple[str, ...]

    @property
    def reason_text(self) -> str:
        return ", ".join(self.reasons) if self.reasons else "no signals"


SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "date or deadline",
        re.compile(
            r"\b(?:by|due|deadline|today|tomorrow|tonight|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"january|february|march|april|may|june|july|august|"
            r"september|october|november|december|"
            r"\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}/\d{1,2})\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ownership or commitment",
        re.compile(
            r"\b(?:i(?:'ll| will| can)|we(?:'ll| will| can)|"
            r"i can|i got|i've got|handle|taking care of|take care of|"
            r"own(?:er|ing)?|assigned|volunteer|responsible)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "task or decision",
        re.compile(
            r"\b(?:need to|needs to|todo|task|action item|follow up|"
            r"send|contact|confirm|book|reserve|order|submit|decided|"
            r"decision|approved|agreed|finalized)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "event",
        re.compile(
            r"\b(?:event|ideathon|hackathon|workshop|meeting|kickoff|"
            r"conference|panel|info session|career fair|retreat)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "sponsor or company",
        re.compile(
            r"\b(?:sponsor|sponsorship|company|partner|vendor|recruiter|"
            r"adobe|google|microsoft|target|amazon|3m|best buy)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "logistics or location",
        re.compile(
            r"\b(?:room|location|venue|building|hall|food|catering|"
            r"transportation|parking|zoom|check-in|capacity)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "funding",
        re.compile(
            r"\b(?:funding|funds|budget|cost|price|invoice|reimburse|"
            r"reimbursement|purchase|payment|paid)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "status or blocker",
        re.compile(
            r"\b(?:blocked|blocker|waiting on|depends on|dependency|"
            r"completed|finished|done|in progress|delayed|postponed|"
            r"cancelled|canceled|moved|changed|update)\b",
            re.IGNORECASE,
        ),
    ),
)


def assess_relevance(
    context: ExtractionContext,
    *,
    reply_is_relevant: bool = False,
) -> RelevanceDecision:
    content = context.content.strip()
    if not content:
        return RelevanceDecision(False, ())

    reasons = [name for name, pattern in SIGNALS if pattern.search(content)]
    if reply_is_relevant:
        reasons.append("reply to relevant message")

    return RelevanceDecision(bool(reasons), tuple(dict.fromkeys(reasons)))
