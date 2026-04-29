# 003. Create `state.py` with `CertificateRequest`, `IssuedCertificate`, `CharmState`

## What

Create `src/state.py` defining the three Pydantic models specified in the spec (`CertificateRequest`, `IssuedCertificate`, `CharmState`) and implement `CharmState.from_charm()`. The `from_charm()` method iterates all active `certificates` (old-interface) relations, calls `get_certificate_requests()` from `certificate_provider.py` to collect pending requests, and (for now) leaves `issued_certificates` empty. Also define `CharmBaseWithState` as specified in the design-pattern instructions.

## Why

Provides the single source of truth for all charm data, following the holistic reconcile pattern (spec: State Model; design-pattern instructions: `state.py` responsibilities).

## Acceptance Criteria

- [ ] `CertificateRequest`, `IssuedCertificate`, and `CharmState` are Pydantic `BaseModel` subclasses with the fields from the spec.
- [ ] `CharmState.from_charm(charm)` returns a `CharmState` aggregating requests from all active old-interface relations.
- [ ] `CharmBaseWithState` abstract class is defined with `state` property and `reconcile()` abstract method.
- [ ] Unit tests cover: no relations → empty state; one relation with two unit requests → both captured; relation with no requests → empty list.

## Files

- `src/state.py` — new file
- `tests/unit/test_state.py` — new file

## Notes

- `CharmState.issued_certificates` is a `dict[str, IssuedCertificate]` keyed by CSR SHA-256 hex (populated in PR 002+ tasks).
- Import `CertificateRequest` from `certificate_provider` or define it in `state.py` and import it in `certificate_provider.py` — either direction works; keep the import cycle-free.
- Pydantic v2 is available via ops extras; use `model_config = ConfigDict(frozen=True)` for immutable state objects.
