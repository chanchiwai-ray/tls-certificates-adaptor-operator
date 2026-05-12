# 002. Delete secret.py

## What

Delete `src/secret.py` entirely. The charm will no longer create or manage any Juju Secrets of
its own.

## How

- Delete `src/secret.py`.
- Remove `from secret import ...` lines from every file that imports it:
  - `src/old_tls_certificate.py`
  - `src/new_tls_certificate.py`
  - `src/charm.py`

Also delete `src/models.py:IssuedCertificate` dataclass (it was only used by
`get_issued_certificates` which is removed in task 004).

Run a project-wide import check:

```bash
tox -e unit
```

## Notes

- After this task the project will not yet compile cleanly because callers of the deleted
  functions have not been updated yet — that is fine; the remaining tasks in this PR fix the
  callers.

## The TODO checklist

- Make the code changes
- Test the change locally
- Make a git commit following conventional commit practice
