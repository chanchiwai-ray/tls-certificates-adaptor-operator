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
- Collects data from relation libraries
- Validates and transforms data into a consistent format using Pydantic models
- Provides a `CharmState` object that represents the complete desired state
- Wraps a `CharmBase` object with a `CharmStateWithState` that includes the state as an attribute for easy access in relation libraries

```python
class CharmState(BaseModel):
  """The pydantic model for charm state.

  Charm state encapsulates all the data about the charm, including config, secret and relation
  data. It is the single source of truth for the charm.
  """

  @classmethod
  def from_charm(cls, charm: ops.CharmBase, ...) -> "CharmState":
      """Create a CharmState from a CharmBase instance."""


class CharmBaseWithState(ops.CharmBase, ABC):
  """The CharmBase than can build a CharmState."""

  @property
  @abstractmethod
  def state(self) -> CharmState | None:
      """The charm state."""

  @abstractmethod
  def reconcile(self, _: ops.HookEvent) -> None:
      """Reconcile configuration."""
```

### `secret.py`

The secret module manages or parse secrets for the charm

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

These libraries abstract the complexity of relation data exchange and provide clean interfaces for the charm to use.

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
