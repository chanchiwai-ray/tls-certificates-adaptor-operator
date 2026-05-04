# 002. Fix `get_certificate_requests()` to parse batch and legacy formats

## What

Rewrite `OldTLSCertificatesRelation.get_certificate_requests()` in `src/old_tls_certificate.py`
to correctly parse both request sub-formats written by OpenStack charms:

- **Batch format**: `cert_requests` databag key contains a JSON-encoded **dict**
  `{"<cn>": {"sans": [...]}, ...}` — used by charmhelpers `CertRequest.get_request()`.
- **Legacy format**: `common_name` and `sans` are direct string keys in the unit databag — used
  by the reactive library for the first cert per unit.

Remove the current list-based parser. Keep the `CERT_REQUEST_KEY` constant import — it is still
the correct key name (`cert_requests`) for the batch format.

## How

Replace the body of `get_certificate_requests()` with the following logic:

```python
def get_certificate_requests(self) -> list[CertificateRequest]:
    requests: list[CertificateRequest] = []
    for relation in self._charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
        for unit in relation.units:
            data = relation.data[unit]

            # --- Legacy format ---
            cn = data.get("common_name", "").strip()
            if cn:
                raw_sans = data.get("sans", "")
                try:
                    sans = json.loads(raw_sans) if raw_sans else []
                    if not isinstance(sans, list):
                        raise ValueError
                except (json.JSONDecodeError, ValueError):
                    logger.warning(
                        "Malformed sans in legacy databag for %s on relation %d; using []",
                        unit.name, relation.id,
                    )
                    sans = []
                requests.append(CertificateRequest(
                    common_name=cn,
                    sans_dns=[str(s) for s in sans],
                    cert_type=OLD_INTERFACE_CERT_TYPE,
                    requirer_unit_name=unit.name,
                    relation_id=relation.id,
                    is_legacy=True,
                ))

            # --- Batch format ---
            raw = data.get(CERT_REQUEST_KEY, "")
            if not raw:
                continue
            try:
                entries = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "Malformed cert_requests JSON for %s on relation %d",
                    unit.name, relation.id,
                )
                continue
            if not isinstance(entries, dict):
                logger.warning(
                    "cert_requests is not a dict for %s on relation %d",
                    unit.name, relation.id,
                )
                continue
            for batch_cn, req in entries.items():
                if not batch_cn or not isinstance(req, dict):
                    continue
                sans = req.get("sans") or []
                if not isinstance(sans, list):
                    logger.warning(
                        "sans is not a list for CN %r from %s on relation %d; wrapping",
                        batch_cn, unit.name, relation.id,
                    )
                    sans = [sans]
                requests.append(CertificateRequest(
                    common_name=batch_cn,
                    sans_dns=[str(s) for s in sans],
                    cert_type=OLD_INTERFACE_CERT_TYPE,
                    requirer_unit_name=unit.name,
                    relation_id=relation.id,
                    is_legacy=False,
                ))
    return requests
```

Keep `CERT_REQUEST_KEY` import (it is still the correct key name for the batch format);
remove the `isinstance(entries, list)` guard and the `cert_type` check from the batch path.

Run unit tests:

```bash
tox -e unit -- tests/unit/test_old_tls_certificate.py
```

## Notes

- `unit.name` is e.g. `cinder/0`; the munged name used in response keys is derived in
  `write_certificate()`, not here.
- Both formats may coexist in the same unit databag: the legacy block and the batch block are
  independent `if` branches (not `elif`).
- Changing `logger.debug` to `logger.warning` for the non-JSON and non-dict cases makes them
  visible in juju debug-log without requiring `--level=DEBUG`.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
