# Playbook format

Playbooks live in `playbooks/`, overlays in `playbooks/overlays/`, and future
ColorStack-specific definitions may live in `playbooks/custom/`.

## Minimal definition

```yaml
key: workshop
name: Workshop
event_type: workshop
version: "1"
detection_keywords: [workshop, hands-on]
requirements:
  - key: venue
    name: Venue
    required: true
    criticality: critical
    ideal_lead_days: 21
    minimum_lead_days: 10
    done_when: [room reservation is confirmed]
    evidence_expected: [current location state]
    next_step: Confirm and document the room reservation.
    evaluation:
      event_fields: [location]
      task_keywords: [room, venue]
      completion_mode: presence
```

## Requirement fields

- `required`: distinguishes mandatory work from best practice
- `criticality`: `critical`, `high`, `medium`, or `low`
- `typical_owner`: suggested team or role
- `ideal_lead_days`, `minimum_lead_days`: urgency thresholds
- `dependencies`: requirement keys in the resolved playbook
- `done_when`: explicit completion criteria
- `common_failure_modes`: planning warnings
- `evidence_expected`: human-readable evidence description
- `sponsor_dependent`: raises urgency on sponsored events
- `event_type_specific`: whether the item belongs only to this event type
- `next_step`: deterministic recommendation

Evaluation config supports:

- `event_fields`: Phase 4 current-state fields
- `task_keywords`: phrases matched against canonical task titles
- `completion_terms`: every term required for term-based completion
- `in_progress_terms`: reserved for future rule refinement
- `completion_mode`: `presence`, `task_completed`, or `terms`

Unspecified metadata receives conservative defaults. Validate before syncing:

```bash
python -m colorstack_ai.playbooks validate
```

## Overlays

An overlay uses:

```yaml
event_type: company_sponsored
overlay: true
```

It contributes requirements without replacing the detected base playbook.

## Extensions and overrides

Use `extends` to inherit a generic playbook. Requirements with matching keys
replace only the supplied fields after inheritance:

```yaml
key: colorstack_workshop
name: ColorStack Workshop
event_type: workshop
version: "1"
extends: [workshop]
requirements:
  - key: venue
    name: Accessible campus room
```

Do not edit a version after it has been synchronized. The database stores a
definition hash and rejects changed content under the same key/version. Increment
`version` for approved changes so historical evaluations remain interpretable.
