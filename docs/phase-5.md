# Phase 5 — Event playbooks

Phase 5 compares current organizational state with versioned expectations for a
well-run event. It identifies evidence-backed completion, missing work,
blockers, urgency, and recommended next steps. It does not generate daily
reports.

## Supported playbooks

Base playbooks:

- ideathon / hackathon
- panel
- workshop
- networking event
- general meeting
- social / board bonding

The company-sponsored overlay can apply alongside any base playbook.

## Evaluation flow

```text
current event and task state
  → conservative event-type detection
  → base playbook plus overlays
  → evidence and completion checks
  → dependency and urgency evaluation
  → weighted readiness
  → current result plus evaluation history
```

Detection uses canonical names, aliases, current state, and resolved fact text.
If multiple base types are equally plausible, the base type remains unknown.

## Requirement statuses

- `complete`: source-linked evidence satisfies the completion rule
- `in_progress`: related work exists without completion evidence
- `missing`: a required item has no evidence
- `blocked`: matching work is explicitly blocked or has a blocked prerequisite
- `not_applicable`: evidence explicitly says the item is unnecessary
- `unknown`: an optional item has neither evidence nor an applicability decision

Mentioning an item is not enough to complete it. A completed matching task can
satisfy a requirement; term-based requirements must contain every configured
completion signal.

## Urgency

Urgency is deterministic. The score combines:

- criticality
- missing or blocked status
- whether the event is inside ideal or minimum lead time
- number of downstream requirements
- sponsor dependency for sponsored events

Scores map to low, medium, high, or critical. Completed and not-applicable work
always has low urgency. The stored rationale explains every contributing rule.

## Readiness

Criticality weights are:

- critical: 4
- high: 3
- medium: 2
- low: 1

Optional requirements use 40% of that weight. Complete work receives full
credit, in-progress work receives 50%, unknown work receives 15%, and missing
or blocked work receives none. Explicitly not-applicable items are excluded
from the denominator.

```text
readiness = earned weighted points / available weighted points × 100
```

## Commands

```bash
python -m colorstack_ai.playbooks list
python -m colorstack_ai.playbooks validate
python -m colorstack_ai.playbooks sync
python -m colorstack_ai.requirements evaluate-all
python -m colorstack_ai.requirements evaluate-event <event-id>
```

Evaluation synchronizes validated playbook versions automatically.

## Verification

```sql
SELECT COUNT(*) FROM playbooks WHERE active;
SELECT COUNT(*) FROM playbook_requirements;
SELECT COUNT(*) FROM event_playbooks;
SELECT status, urgency, COUNT(*)
FROM event_requirement_state
GROUP BY status, urgency;
SELECT readiness_score, critical_gap_count, finished_at
FROM requirement_evaluation_runs
ORDER BY finished_at DESC
LIMIT 10;
```

Manual seeded verification confirmed:

- missing judges and judging rubric were identified
- explicit judge completion changed judges to complete with message evidence
- moving the event inside minimum lead time increased rubric urgency
- sponsor state added the company-sponsored overlay
- repeated evaluation preserved current results and appended history

## Limitations

- Completion rules are deterministic and require calibration with more events.
- Optional items remain unknown until evidence or an applicability decision
  exists.
- There is no human review interface for applicability overrides.
- Historical learning and automatic playbook tuning are deferred to Phase 6.
- Daily reports and outbound recommendations are not part of this phase.
