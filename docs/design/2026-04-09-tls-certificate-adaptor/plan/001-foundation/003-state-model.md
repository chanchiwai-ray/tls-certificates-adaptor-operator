# 003. Create `state.py` with `CharmState` and `CharmBaseWithState`

## What

Create `src/state.py` defining `CharmState` (Pydantic model) and `CharmBaseWithState` (abstract base class). `CharmState` uses `CertificateRequest` and `IssuedCertificate` imported from `certificate_provider.py`. Implement `CharmState.from_charm()` which iterates all active `certificates` (old-interface) relations, calls `get_certificate_requests()` to collect pending requests, and (for now) leaves `issued_certificates` empty. Also define `CharmBaseWithState` as specified in the design-pattern instructions.

Note: `CertificateRequest` and `IssuedCertificate` are defined in `certificate_provider.py` (task 002) and imported into `state.py` to avoid circular imports.

## Why

Provides the single source of truth for all charm data, following the holistic reconcile pattern (spec: State Model; design-pattern instructions: `state.py` responsibilities).

## Acceptance Criteria

- [x] `CharmState` is a Pydantic `BaseModel` subclass with `certificate_requests: list[CertificateRequest]` and `issued_certificates: dict[str, IssuedCertificate]` fields.
- [x] `CertificateRequest` and `IssuedCertificate` are defined in `certificate_provider.py` and imported into `state.py` (no circular import).
- [x] `CharmState.from_charm(charm)` returns a `CharmState` aggregating requests from all active old-interface relations.
- [x] `CharmBaseWithState` abstract class is defined with `state` property and `reconcile()` abstract method.
- [x] Unit tests cover: no relations → empty state; one relation with two unit requests → both captured; relation with no requests → empty list.

## Files

- `src/state.py` — new file (`CharmState`, `CharmBaseWithState` only; models live in `certificate_provider.py`)
- `tests/unit/test_state.py` — new file

## Notes

- `CharmState.issued_certificates` is a `dict[str, IssuedCertificate]` keyed by CSR SHA-256 hex fingerprint (populated in PR 002+ tasks).
- `CertificateRequest` and `IssuedCertificate` are imported from `certificate_provider` at the top of `state.py` — no local imports.
- Pydantic v2 is available via ops extras; use `model_config = ConfigDict(frozen=True)` for immutable state objects.
