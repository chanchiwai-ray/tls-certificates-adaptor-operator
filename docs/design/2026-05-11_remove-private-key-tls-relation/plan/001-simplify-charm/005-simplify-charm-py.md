# 005. Simplify charm.py

## What

Update the main charm to remove all private-key wiring, the `certificate_denied` handler, the
`process_relation` loop, and the `get_issued_certificates` call; wire up the new
`update_certificate_requests` method and simplify `_on_certificates_relation_broken`.

## How

**`src/charm.py`**:

- Remove `from secret import get_or_generate_private_key`.
- Remove `self._charm_key_pem = get_or_generate_private_key(self)`.
- Remove `CertificateDeniedEvent` from the `charmlibs.interfaces.tls_certificates` import.
- Remove `private_key_pem` and `certificate_requests` arguments from
  `NewTLSCertificatesRelation(...)`.
- Remove `private_key_pem` argument from `OldTLSCertificatesRelation(...)`.
- Remove `self.framework.observe(self.tls_certificates.on.certificate_denied, ...)`.
- Remove `_on_certificate_denied` method.

- `_on_certificate_available`: remove `self.reconcile()`; replace with
  `self.unit.status = ops.ActiveStatus()`.

- `_on_certificates_relation_broken`: remove `self._old_handler.revoke_csr_mappings(...)`;
  keep only `self.reconcile()`.

- `reconcile`: replace the `process_relation` loop and `get_issued_certificates` block with:
  ```python
  requests = self._old_handler.get_certificate_requests()
  self._upstream_handler.update_certificate_requests(requests)

  if provider_certs := self.tls_certificates.get_provider_certificates():
      first = provider_certs[0]
      full_ca_pem = build_ca_bundle(
          str(first.ca), [str(c) for c in first.chain],
          str(first.certificate), self.state.extra_ca_certificates,
      )
      self._old_handler.write_ca(ca=full_ca_pem)

  self.unit.status = ops.ActiveStatus()
  ```

Run all unit tests:

```bash
tox -e unit
```

## Notes

- `self.state` is still used for `extra_ca_certificates` — keep the `state` property and
  `CharmState` import. `certificate_requests` is no longer read from `self.state` in `reconcile`;
  it is obtained directly from `self._old_handler.get_certificate_requests()`. `CharmState`
  still stores `certificate_requests` (populated via the same call in `from_charm`), but
  `reconcile` should not call `get_certificate_requests()` twice — use the local `requests`
  variable for both `update_certificate_requests` and any other use within `reconcile`.
- After this task, all source changes are complete and the full test suite should pass.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
