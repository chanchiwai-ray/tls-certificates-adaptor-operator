---
applyTo: src/**/*.py, tests/**/*.py
---

# Lessons Learned

## Do not monkeypatch by direct class attribute assignment in tests

**Bad** — brittle in parallel runs; requires manual save/restore; leaks if the test raises before `finally`:

```python
original = MyCharm.reconcile
MyCharm.reconcile = lambda self, *_: ...  # type: ignore
try:
    ctx.run(ctx.on.install(), state)
finally:
    MyCharm.reconcile = original  # type: ignore
```

**Good** — use `unittest.mock.patch.object` as a context manager; patch is always reverted, even on failure, and is scoped to the `with` block:

```python
from unittest.mock import patch

with patch.object(MyCharm, "reconcile", lambda self, *_: ...):
    ctx.run(ctx.on.install(), state)
```

Alternatively, use pytest's `monkeypatch` fixture when the patched value must be inspected or changed mid-test:

```python
def test_something(monkeypatch):
    monkeypatch.setattr(MyCharm, "reconcile", lambda self, *_: ...)
    ctx.run(ctx.on.install(), state)
```

## Do not use local imports to break circular dependencies

If a local import inside a function is needed to avoid a circular dependency, that is a signal the module structure is wrong. Restructure instead.

**Bad** — hides the dependency, makes the import graph hard to reason about:

```python
# state.py
class CharmState(BaseModel):
    @classmethod
    def from_charm(cls, charm):
        from certificate_provider import get_certificate_requests  # local import to avoid cycle
        ...
```

**Good** — break the cycle by moving the shared types to the module that has no upstream dependencies, then import at the top level:

```python
# certificate_provider.py  ← owns the data models; imports nothing from state.py
class CertificateRequest(BaseModel): ...

# state.py  ← depends on certificate_provider, not the other way around
from certificate_provider import CertificateRequest, get_certificate_requests
```
