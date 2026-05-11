# 004. Rewrite NewTLSCertificatesRelation

## What

Rewrite `NewTLSCertificatesRelation` to construct the library with no private key, expose an
`update_certificate_requests` method, and re-derive routing info from live relation data at
`certificate_available` time instead of reading a mapping secret.

## How

**`src/new_tls_certificate.py`**:

- `__init__`: remove `private_key_pem` and `certificate_requests` parameters; construct
  `TLSCertificatesRequiresV4` with `certificate_requests=[]` and no `private_key` argument;
  remove `refresh_events` wiring for old-relation events.

- Add `update_certificate_requests(requests: list[CertificateRequest]) -> None`:
  ```python
  def update_certificate_requests(self, requests: list[CertificateRequest]) -> None:
      attrs = []
      for cr in requests:
          dns_sans, ip_sans = classify_sans(cr.sans)
          attrs.append(CertificateRequestAttributes(
              common_name=cr.common_name,
              sans_dns=dns_sans if dns_sans else None,
              sans_ip=ip_sans if ip_sans else None,
              add_unique_id_to_subject_name=False,
          ))
      self._tls.certificate_requests = attrs
      self._tls.sync()
  ```

- `handle_certificate_available`: replace the secret lookup with live-data matching:
  1. Extract `csr = event.certificate_signing_request`.
  2. Parse `common_name = str(csr.common_name)` and reconstruct `sans` as
     `sorted((csr.sans_dns or set()) | (csr.sans_ip or set()))`.
  3. Call `old_handler.get_certificate_requests()` and iterate to find the first
     `CertificateRequest` where `cr.common_name == common_name` and
     `sorted(cr.sans) == sans`.
  4. If no match: log error and return.
  5. Check the old-interface relation is still active; if not: log and return.
  6. Retrieve key: `key = str(self._tls.private_key)`.
  7. Call `write_client_cert` or `write_certificate` using `cr.relation_id`,
     `cr.requirer_unit_name`, `cr.is_legacy`, `cr.is_client`.
  8. Call `old_handler.write_ca(ca=full_ca_pem)`.

- Delete `handle_certificate_denied` and `get_issued_certificates`.
- Remove all imports from `secret`; remove `IssuedCertificate` from `models` import;
  remove `CertificateDeniedEvent` and `PrivateKey` imports.

Run unit tests:

```bash
tox -e unit -- tests/unit/test_new_tls_certificate.py -x
```

## Notes

- `csr.sans_dns` and `csr.sans_ip` on `CertificateSigningRequest` are `frozenset[str] | None` —
  guard with `or set()` before combining.
- `str(self._tls.private_key)` returns `'None'` in the ops testing harness until a real
  `sync()` has run and the library has created its secret — this is acceptable for unit tests
  which only assert field presence.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
