# 004. Observe old-interface relation events in `charm.py`, set unit status

## What

Update `src/charm.py` so that `TLSCertificateAdaptorCharm` inherits from `CharmBaseWithState`, observes `certificates_relation_changed` and `certificates_relation_broken` events, and calls `reconcile()` from each handler. The `reconcile()` implementation calls `CharmState.from_charm()` to build the state, then sets `WaitingStatus("Waiting for upstream TLS provider")` if the `certificates-upstream` relation is not yet established, or `ActiveStatus()` once it is (the full reconcile logic is added in later PRs; this task wires the skeleton). Update `_on_install` and `_on_config_changed` to delegate to `reconcile()`.

## Why

Wires the event-to-reconcile flow required by the holistic pattern so that the charm responds to old-interface relation events from the first PR onwards (spec: Events Handled; design-pattern instructions: `charm.py` responsibilities).

## Acceptance Criteria

- [x] `charm.py` observes `certificates_relation_changed` and `certificates_relation_broken`.
- [x] `reconcile()` calls `CharmState.from_charm()` without error.
- [x] Unit status is `WaitingStatus` when no `certificates-upstream` relation exists, `ActiveStatus` when it does.
- [x] `tox -e unit` passes; coverage ≥ 90% for `src/charm.py`.

## Files

- `src/charm.py` — update event observers and reconcile skeleton
- `tests/unit/test_charm.py` — update/expand unit tests (renamed from `test_base.py`)

## Notes

- Use `self.model.relations[UPSTREAM_RELATION_NAME]` to check if the upstream relation exists.
- The class must implement `CharmBaseWithState.state` property and `reconcile()` abstract method.
- Keep the `reconcile()` body minimal in this task — full certificate logic is added in PRs 002–004.
