# 003. Fix `write_certificate()` and add `write_ca()`

## What

Rewrite `OldTLSCertificatesRelation.write_certificate()` in `src/old_tls_certificate.py` to
produce the response format expected by reactive `tls-certificates` (v1) requirers, branching on
the `is_legacy` flag from the `CertificateRequest` model. Add a new `write_ca()` method that
propagates the upstream CA cert to all active old-interface relations.

## How

### `write_certificate()` signature change

Add `is_legacy: bool` parameter:

```python
def write_certificate(
    self,
    relation_id: int,
    requirer_unit_name: str,
    common_name: str,
    cert: str,
    key: str,
    ca: str,
    chain: str = "",
    is_legacy: bool = False,
) -> None:
```

### Legacy path (`is_legacy=True`)

Write the individual `.server.cert` / `.server.key` keys used by the reactive `server_certs`
property for the first-cert backwards-compat path:

```python
munged = requirer_unit_name.replace("/", "_")
relation.data[self._charm.unit][f"{munged}.server.cert"] = cert
relation.data[self._charm.unit][f"{munged}.server.key"] = key
relation.data[self._charm.unit]["ca"] = ca
if chain:
    relation.data[self._charm.unit]["chain"] = chain
```

### Batch path (`is_legacy=False`)

Merge the new cert into the existing `{munged}.processed_requests` dict (so that multiple CNs
from the same requirer unit accumulate in a single key):

```python
munged = requirer_unit_name.replace("/", "_")
key_name = f"{munged}{PROCESSED_REQUESTS_SUFFIX}"
existing_raw = relation.data[self._charm.unit].get(key_name) or "{}"
try:
    existing = json.loads(existing_raw)
    if not isinstance(existing, dict):
        existing = {}
except json.JSONDecodeError:
    existing = {}
existing[common_name] = {"cert": cert, "key": key}
relation.data[self._charm.unit][key_name] = json.dumps(existing)
relation.data[self._charm.unit]["ca"] = ca
if chain:
    relation.data[self._charm.unit]["chain"] = chain
```

### New `write_ca()` method

```python
def write_ca(self, ca: str, chain: str = "") -> None:
    """Write the upstream CA cert to all active old-interface relations."""
    for relation in self._charm.model.relations[OLD_INTERFACE_RELATION_NAME]:
        relation.data[self._charm.unit]["ca"] = ca
        if chain:
            relation.data[self._charm.unit]["chain"] = chain
```

Remove the old `PROCESSED_REQUESTS_SUFFIX` usage from the broken list-payload path; the constant
remains correct and is still used for the batch path.

Run unit tests:

```bash
tox -e unit -- tests/unit/test_old_tls_certificate.py
```

## Notes

- The reactive requirer reads `ca` and `chain` as top-level keys on the **provider unit databag**
  — not nested inside `processed_requests`. Writing `ca` in both paths is correct.
- `PROCESSED_REQUESTS_SUFFIX` is defined in `constants.py` as `".processed_requests"` — the
  resulting key `"{munged}.processed_requests"` matches what `TlsRequires.server_certs` reads.
- `chain` should be written as a single concatenated PEM string (multiple PEM blocks joined with
  newlines) if the upstream provides a chain list.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
