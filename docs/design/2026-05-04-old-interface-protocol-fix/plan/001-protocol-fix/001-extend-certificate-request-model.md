# 001. Add `is_legacy` field to `CertificateRequest` model

## What

Add an `is_legacy: bool` field (default `False`) to the `CertificateRequest` Pydantic model in
`src/models.py`. This flag distinguishes between the legacy single-cert request format (direct
`common_name` databag key) and the batch request format (`cert_requests` dict). The flag is
threaded through to the write path so `write_certificate()` knows which response keys to use.

## How

In `src/models.py`, add the field to `CertificateRequest`:

```python
class CertificateRequest(BaseModel):
    ...
    is_legacy: bool = False  # True → legacy format; False → batch format
```

No other files change in this task. Downstream callers that construct `CertificateRequest` objects
without `is_legacy` will continue to work (the field defaults to `False`).

Run the existing unit tests to confirm nothing is broken:

```bash
tox -e unit -- tests/unit/test_state.py
```

## Notes

Defaulting to `False` (batch) means any existing mapping secrets written before this fix — which
have no `is-legacy` key — will produce `is_legacy=False` when read back, which is the safe
fallback (batch response format is preferred for new-format requesters).

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
