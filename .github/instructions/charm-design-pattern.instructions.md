---
description: Common design pattern for charm.
applyTo: "src/**/*.py"
---

# Common design pattern for charm

Development of charms follows a consistent design pattern that separates concerns into distinct modules, making the codebase maintainable and testable. The design emphasizes:

- **Single source of truth**: All configuration and relation data is aggregated into a single state object
- **Separation of concerns**: Clear boundaries between charm logic, state management, and workload configuration
- **Declarative configuration**: The workload is configured based on the desired state, not through imperative commands

## Architecture pattern

Both charms implement the same architectural pattern:

```{mermaid}
graph LR
  E[Events] --> H[Observed in charm.py]
  H --> R[Relation Libraries]
  H --> C[Configuration]
  H --> SS[Secret]
  R --> S[State Module]
  C --> S
  SS --> S
  S --> W[Workload/Service Module]
  W --> T[Templates]
  W --> WL[Workload/System]

  style S fill:#ffe1e1
  style W fill:#e1f5ff
  style H fill:#fff4e1
```

The flow of data through the charm follows this pattern:

1. **Event handlers**: Juju events (`config-changed`, `relation-changed`, `secret-changed`) are observed in `charm.py`
2. **Data collection**: Handlers gather data from configuration options and relation libraries
3. **State aggregation**: All data is combined into a single `CharmState` object in the `state.py` module
4. **Workload configuration**: The workload module (`service.py` or `workload.py`) receives the state and configures the service accordingly

## Module responsibilities

### `charm.py`

The main charm module coordinates the overall charm behavior:

- Observes Juju lifecycle events (`install`, `config-changed`, `upgrade`)
- Observes relation events (`relation-joined`, `relation-changed`, `relation-broken`)
- Observes secret events (`secret-changed`)
- Initializes relation libraries and helper objects
- Delegates workload configuration to the service/workload module

### `state.py`

The state module provides a single source of truth for all charm data:

- Aggregates charm configuration options
- Collects data from relation handlers passed in as arguments (dependency injection — no direct class instantiation inside `from_charm`)
- Validates and transforms data into a consistent format using Pydantic models
- Provides a `CharmState` object that represents the complete desired state
- Wraps a `CharmBase` object with a `CharmBaseWithState` that includes the state as an attribute for easy access in relation libraries

```python
class CharmState(BaseModel):
  # fields populated from relation handlers and config

  @classmethod
  def from_charm(
    cls,
    <relation-handler-a>: RelationHandlerA,
    <relation-handler-b>: RelationHandlerB,
    # ... other handlers / config
  ) -> "CharmState":
    # Collect data by calling methods on the injected handlers.
    # Never instantiate handler classes here; accept them as arguments.
    data_a = relation_handler_a.get_data()
    data_b = relation_handler_b.get_data()
    return cls(field_a=data_a, field_b=data_b)


class CharmBaseWithState(ops.CharmBase, ABC):
  """The CharmBase that can build a CharmState."""

  @property
  @abstractmethod
  def state(self) -> CharmState | None:
    """The charm state."""

  @abstractmethod
  def reconcile(self, _: ops.HookEvent) -> None:
    """Reconcile configuration."""
```

Example usage with caching of `CharmState` in `charm.py`:

```python
class MyCharm(CharmBaseWithState):
  def __init__(self, *args):
    super().__init__(*args)
    # Handlers are constructed in __init__ so they exist before state is accessed.
    self.handler_a = RelationHandlerA(...)
    self.handler_b = RelationHandlerB(...)

  @property
  def state(self) -> CharmState | None:
    if self._state is None:
      self._state = CharmState.from_charm(self.handler_a, self.handler_b)
    return self._state
```

### `secret.py`

The secret module manages or parses secrets for the charm

### `config.py`

The configuration module defines the schema for charm configuration options and provides validation logic. It ensures that all configuration data is consistent and can be easily accessed from the state module.

```python
"""Charm config option module."""

import logging
from typing import Optional

from ops import Secret
from pydantic import AnyUrl, BaseModel, ConfigDict, field_validator

logger = logging.getLogger(__name__)


class InvalidCharmConfigError(Exception):
  """Exception raised when the charm configuration is invalid."""


class CharmConfig(BaseModel):
  """The pydantic model for charm config.

  Note that the charm config should be loaded via ops.CharmBase.load_config().
  """
```

### `service.py` / `workload.py`

The workload module configures the service based on the charm state:

- Receives the `CharmState` object from the charm
- Renders configuration templates with state data
- Manages the lifecycle of the workload (install, configure, restart)
- Interacts with the workload (systemd service for VM, Pebble container for K8s)

### Utility modules

Utility modules provide shared functionality such as constants, logging, and common helper functions.

### Relation handlers

Relation handlers encapsulate all read/write logic for a relation endpoint and are passed into `CharmState.from_charm` as arguments (dependency injection). This keeps `state.py` free of direct imports of handler classes and makes the state straightforward to test with mock handlers.

Each handler is constructed in `charm.py`'s `__init__` and receives the charm instance as its first argument. The handler stores `self._charm` and instantiates any third-party library or performs any relation look-up **inside `__init__`** — not outside. `state.py` never needs to know how relations are looked up or how libraries are initialised.

```python
from ... import RelationLibrary

class <RelationHandler>:
  """Encapsulates read/write access to a relation endpoint."""

  def __init__(self, charm: ops.CharmBase, <other_dependencies>) -> None:
    self._charm = charm
    # Instantiate the library or bind the relation here, not in charm.py.
    self._lib = RelationLibrary(charm, <other_dependencies>)

  def get_<data>(self) -> <DataModel> | None:
    # Read and parse data from the relation databag or library.
    # Derive relation references from self._charm (e.g. self._charm.model.relations[...]).
    # Return None (or an empty collection) on missing / malformed data; never raise.
    ...

  def write_<data>(self, <fields>) -> None:
    # Write data back into the relation databag or via the library.
    # Derive relation references from self._charm (e.g. self._charm.model.get_relation(...)).
    ...
```

In `charm.py`, handlers are created with `self` as the charm and stored as attributes. The state property calls `CharmState.from_charm` with those handler instances:

```python
class MyCharm(CharmBaseWithState):
  def __init__(self, *args):
    super().__init__(*args)
    self._handler_a = RelationHandlerA(self, <other_dependencies>)
    self._handler_b = RelationHandlerB(self, <other_dependencies>)
    # Any library instance needed for event observation can be retrieved
    # from the handler via a property.
    self.lib = self._handler_b.lib

  @property
  def state(self) -> CharmState | None:
    if self._state is None:
      self._state = CharmState.from_charm(self._handler_a, self._handler_b)
    return self._state
```

Multiple handlers (one per endpoint or interface version) can be passed to `CharmState.from_charm` when a charm bridges more than one relation interface.

### Template system

Charms should use Jinja2 templates for configuration files. These templates are stored in the `src/templates/` directory,
and the workload module renders templates with the charm state as context. The rendered files are installed in the
appropriate locations.

### Error handling

Charms should implement consistent error handling:

- Configuration validation errors are caught and result in a `BlockedStatus`
- Missing required relations result in a `BlockedStatus` with a clear message
- Runtime errors are logged and reported through the unit status

This ensures that operators have clear visibility into charm state and can take corrective action when needed.

## Put it all together

The configuration flow in both charms follows this sequence:

```{mermaid}
sequenceDiagram
  participant J as Juju
  participant C as charm.py
  participant S as state.py
  participant W as workload / service module
  participant WL as Workload / Service

  J->>C: Event (config-changed, relation-changed, secret-changed)
  C->>C: Observe event
  C->>S: CharmState.from_charm()
  S->>S: Load config (config.py)
  S->>S: Gather relation data (relation libraries)
  S->>S: Gather secret data (secret.py)
  S->>S: Validate and transform
  S->>C: Return CharmState
  C->>W: configure(state)
  W->>W: Render templates
  W->>WL: Apply configuration
  W->>WL: Restart if needed
  WL->>C: Service status
  C->>J: Set unit status
```

This pattern ensures that:

- Configuration is always derived from the current state
- All changes go through the same validation and transformation logic
- The workload is configured holistically rather than incrementally
