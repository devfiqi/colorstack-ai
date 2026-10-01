from datetime import datetime

from colorstack_ai.briefing.models import BriefEventSection, DailyBrief
from colorstack_ai.reasoning.models import RecommendedAction

DISCORD_MESSAGE_LIMIT = 2000


def _date_label(value: datetime) -> str:
    return value.strftime("%b %d").replace(" 0", " ").upper()


def _action_line(action: RecommendedAction, number: int) -> str:
    owner = action.owner_name or action.owner_discord_id
    suffix = f" — {owner}" if owner else ""
    if action.deadline is not None:
        suffix += f" (by {action.deadline.strftime('%b %d').replace(' 0', ' ')})"
    return f"{number}. {action.title}{suffix}"


def _event_block(section: BriefEventSection) -> str:
    lines = [f"**{section.event_name}**"]
    for item in [*section.updates, *section.unresolved][:5]:
        lines.append(f"• {item}")
    if section.next_actions:
        lines.append("**Next:**")
        lines.extend(
            _action_line(action, index)
            for index, action in enumerate(section.next_actions[:3], start=1)
        )
    return "\n".join(lines)


def format_daily_brief(brief: DailyBrief) -> str:
    blocks = [f"**COLORSTACK EXEC BRIEF — {_date_label(brief.generated_at)}**"]
    if brief.summary:
        blocks.append(brief.summary)

    for label, sections in (
        ("CRITICAL", brief.critical_events),
        ("HIGH", brief.high_events),
    ):
        if sections:
            blocks.append(f"**{label}**")
            blocks.extend(_event_block(section) for section in sections)

    if brief.notable_changes:
        lines = ["**WHAT CHANGED**"]
        lines.extend(f"• {item}" for item in brief.notable_changes[:5])
        blocks.append("\n".join(lines))

    if brief.top_priorities:
        lines = ["**TODAY'S TOP 3**"]
        lines.extend(
            _action_line(action, index)
            for index, action in enumerate(brief.top_priorities[:3], start=1)
        )
        blocks.append("\n".join(lines))

    if not brief.critical_events and not brief.high_events and not brief.top_priorities:
        blocks.append("No critical or high-priority operational items today.")
    return "\n\n".join(blocks)


def split_discord_messages(
    text: str,
    limit: int = DISCORD_MESSAGE_LIMIT,
) -> list[str]:
    if limit < 100:
        raise ValueError("Discord message limit must be at least 100 characters.")
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(block) <= limit:
            current = block
            continue
        for line in block.splitlines():
            while len(line) > limit:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(line[:limit])
                line = line[limit:]
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > limit:
                chunks.append(current)
                current = line
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks
