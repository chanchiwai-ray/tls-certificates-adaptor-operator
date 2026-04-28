# GitHub Actions Reference: canonical/craft-actions & canonical/charming-actions

Research date: 2026-03-25

---

## Table of Contents

1. [canonical/craft-actions](#1-canonicalcraft-actions)
   - [charmcraft/pack](#11-charmcraftpack)
   - [charmcraft/setup](#12-charmcraftsetup)
2. [canonical/charming-actions](#2-canonicalcharming-actions)
   - [channel](#21-channel)
   - [upload-charm](#22-upload-charm)
   - [promote-charm](#23-promote-charm)
   - [release-charm](#24-release-charm)
   - [check-libraries](#25-check-libraries)
   - [release-libraries](#26-release-libraries)
   - [upload-bundle](#27-upload-bundle)
   - [dump-logs](#28-dump-logs)
   - [get-charm-paths](#29-get-charm-paths)
3. [Full Workflow Patterns](#3-full-workflow-patterns)
4. [References](#4-references)

---

## 1. canonical/craft-actions

Repository: https://github.com/canonical/craft-actions
Branch used for `@main` pin: `main`

### 1.1 charmcraft/pack

**`uses:` path:** `canonical/craft-actions/charmcraft/pack@main`

Installs LXD and Charmcraft, then runs `charmcraft pack` in the specified directory. Caches the Charmcraft shared cache between runs using `actions/cache`.

**Inputs:**

| Input         | Required | Default       | Description                                                                      |
| ------------- | -------- | ------------- | -------------------------------------------------------------------------------- |
| `path`        | No       | `.`           | Path within the repository where `charmcraft.yaml` lives.                        |
| `verbosity`   | No       | `trace`       | Build verbosity: `quiet`, `brief`, `verbose`, `debug`, or `trace`.               |
| `channel`     | No       | `stable`      | Snap channel to install Charmcraft from (e.g. `latest/stable`, `3.x/candidate`). |
| `revision`    | No       | `''`          | Pin a specific Charmcraft snap revision. Overrides `channel`.                    |
| `lxd-channel` | No       | `5.21/stable` | LXD snap channel to install.                                                     |

**Outputs:**

| Output                | Description                                         |
| --------------------- | --------------------------------------------------- |
| `charms`              | Space-delimited list of packed `.charm` file names. |
| `charmcraft-revision` | The Charmcraft snap revision that was installed.    |
| `lxd-revision`        | The LXD snap revision that was installed.           |

**Minimal usage example:**

```yaml
- name: Pack charm
  id: pack
  uses: canonical/craft-actions/charmcraft/pack@main

- name: Upload packed charm artifact
  uses: actions/upload-artifact@v4
  with:
    name: charm
    path: "*.charm"
```

**Full example with all inputs:**

```yaml
- name: Pack charm
  id: pack
  uses: canonical/craft-actions/charmcraft/pack@main
  with:
    path: "."
    channel: "latest/stable"
    revision: "" # leave empty to track channel
    lxd-channel: "5.21/stable"
    verbosity: "trace"

- name: Show outputs
  run: |
    echo "Packed: ${{ steps.pack.outputs.charms }}"
    echo "Charmcraft rev: ${{ steps.pack.outputs.charmcraft-revision }}"
    echo "LXD rev: ${{ steps.pack.outputs.lxd-revision }}"
```

> **Note:** Only works on Linux runners with `snapd` available (`ubuntu-*`). The action internally calls `canonical/craft-actions/charmcraft/setup` before packing.

---

### 1.2 charmcraft/setup

**`uses:` path:** `canonical/craft-actions/charmcraft/setup@main`

Installs LXD and Charmcraft without building anything. Use when you need Charmcraft available for subsequent steps (e.g. fetching libraries or custom commands).

**Inputs:**

| Input         | Required | Default         | Description                              |
| ------------- | -------- | --------------- | ---------------------------------------- |
| `channel`     | No       | `latest/stable` | Charmcraft snap channel.                 |
| `revision`    | No       | `''`            | Pin a specific Charmcraft snap revision. |
| `lxd-channel` | No       | `5.21/stable`   | LXD snap channel.                        |

**Outputs:**

| Output                | Description                                      |
| --------------------- | ------------------------------------------------ |
| `charmcraft-revision` | The Charmcraft snap revision that was installed. |
| `lxd-revision`        | The LXD snap revision that was installed.        |

**Minimal usage example:**

```yaml
- uses: canonical/craft-actions/charmcraft/setup@main
  id: setup
  with:
    channel: "latest/stable"

- run: charmcraft fetch-libs
```

---

## 2. canonical/charming-actions

Repository: https://github.com/canonical/charming-actions
The README examples pin to `@2.2.0`; use `@main` for latest (HEAD SHA: `38f996620f6c919bec65bd3a6750eb8b1cceba22` as of research date).

> **Prerequisites:** Add a Charmhub token as a repository secret (conventionally `CHARMCRAFT_TOKEN` or `CHARMHUB_TOKEN`). Generate it with `charmcraft login --export`. See [Remote env auth docs](https://juju.is/docs/sdk/remote-env-auth).

---

### 2.1 channel

**`uses:` path:** `canonical/charming-actions/channel@2.6.0`

Determines which Charmhub channel to publish to based on the git ref / event type. Does **not** mutate any state itself — it only outputs a channel name. Use together with `upload-charm`.

**Inputs:** None

**Outputs:**

| Output | Description                                                                               |
| ------ | ----------------------------------------------------------------------------------------- |
| `name` | Calculated Charmhub channel string (e.g. `latest/edge`, `2.0/edge`, `latest/edge/pr-42`). |

**Branch-to-channel mapping:**

| Event          | Head/Branch | Base           | → Channel                 |
| -------------- | ----------- | -------------- | ------------------------- |
| `push`         | —           | default branch | `latest/edge`             |
| `push`         | —           | `track/<name>` | `<name>/edge`             |
| `push`         | —           | any other      | _(action fails)_          |
| `pull_request` | any         | `track/<name>` | `<name>/edge/pr-<number>` |
| `pull_request` | any         | any other      | `latest/edge/pr-<number>` |

**Minimal usage example:**

```yaml
- name: Select Charmhub channel
  id: channel
  uses: canonical/charming-actions/channel@2.6.0

- name: Upload charm
  uses: canonical/charming-actions/upload-charm@2.6.0
  with:
    credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
    channel: ${{ steps.channel.outputs.name }}
```

---

### 2.2 upload-charm

**`uses:` path:** `canonical/charming-actions/upload-charm@2.6.0`

Packs (or accepts pre-built) a charm and uploads it to Charmhub. Optionally uploads OCI image resources. Creates a GitHub tag and release on publish.

**Inputs:**

| Input                | Required | Default         | Description                                                                                                                         |
| -------------------- | -------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `credentials`        | **Yes**  | —               | Charmhub credentials from `charmcraft login --export`.                                                                              |
| `github-token`       | **Yes**  | —               | GitHub token for auto-tagging releases.                                                                                             |
| `channel`            | No       | `latest/edge`   | Charmhub channel to publish to.                                                                                                     |
| `charm-path`         | No       | `.`             | Path to the charm source directory.                                                                                                 |
| `built-charm-path`   | No       | —               | Comma-separated paths to pre-built `.charm` files. If set, skips `charmcraft pack`. Supports multiple: `/tmp/a.charm,/tmp/b.charm`. |
| `destructive-mode`   | No       | `true`          | Whether to run `charmcraft pack` in destructive mode.                                                                               |
| `charmcraft-channel` | No       | `latest/stable` | Snap channel for installing Charmcraft.                                                                                             |
| `upload-image`       | No       | `true`          | Whether to upload OCI image resources to Charmhub.                                                                                  |
| `pull-image`         | No       | `true`          | Whether to pull OCI images before upload.                                                                                           |
| `github-tag`         | No       | `true`          | Whether to create a GitHub tag/release when publishing.                                                                             |
| `tag-prefix`         | No       | —               | Tag prefix for multi-charm repos using a matrix.                                                                                    |
| `resource-overrides` | No       | `''`            | Comma-separated static resource revision overrides, e.g. `promql-transform:2,prometheus-image:12`.                                  |

**Outputs:** None

**Minimal usage example:**

```yaml
- name: Upload charm to Charmhub
  uses: canonical/charming-actions/upload-charm@2.6.0
  with:
    credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
    channel: "latest/edge"
```

**Using with a pre-built charm (from `charmcraft/pack`):**

```yaml
- name: Pack charm
  id: pack
  uses: canonical/craft-actions/charmcraft/pack@main

- name: Upload pre-built charm
  uses: canonical/charming-actions/upload-charm@2.6.0
  with:
    credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
    channel: "latest/edge"
    built-charm-path: ${{ steps.pack.outputs.charms }}
```

---

### 2.3 promote-charm

**`uses:` path:** `canonical/charming-actions/promote-charm@2.6.0`

Promotes an already-released charm from one Charmhub channel to another. Covers **all** base/architecture combinations that exist in the origin channel. Designed for `workflow_dispatch` triggers.

> **Note:** Promotion covers all existing base+arch combinations. Bases that don't have an open channel in the destination are silently skipped.

**Inputs:**

| Input                 | Required | Default       | Description                                                      |
| --------------------- | -------- | ------------- | ---------------------------------------------------------------- |
| `credentials`         | **Yes**  | —             | Charmhub credentials.                                            |
| `origin-channel`      | **Yes**  | —             | Source channel in `track/risk` format (e.g. `latest/candidate`). |
| `destination-channel` | **Yes**  | —             | Target channel in `track/risk` format (e.g. `latest/stable`).    |
| `charm-path`          | No       | `.`           | Path to charm directory (needed for metadata).                   |
| `charmcraft-channel`  | No       | `latest/edge` | Snap channel for installing Charmcraft.                          |

**Outputs:** None

**Minimal usage example:**

```yaml
name: Promote charm

on:
  workflow_dispatch:
    inputs:
      origin-channel:
        description: "Origin channel (e.g. latest/candidate)"
        required: true
      destination-channel:
        description: "Destination channel (e.g. latest/stable)"
        required: true

jobs:
  promote:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Promote charm
        uses: canonical/charming-actions/promote-charm@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          origin-channel: ${{ github.event.inputs.origin-channel }}
          destination-channel: ${{ github.event.inputs.destination-channel }}
```

---

### 2.4 release-charm

**`uses:` path:** `canonical/charming-actions/release-charm@main`

Releases an already-uploaded charm revision to a different channel. Unlike `promote-charm`, this targets a specific base/architecture combination and updates the GitHub release tag with channel + timestamp. Designed for `workflow_dispatch` triggers.

**Inputs:**

| Input                 | Required | Default            | Description                             |
| --------------------- | -------- | ------------------ | --------------------------------------- |
| `credentials`         | **Yes**  | —                  | Charmhub credentials.                   |
| `github-token`        | **Yes**  | —                  | GitHub token for updating release tags. |
| `origin-channel`      | **Yes**  | —                  | Source channel in `track/risk` format.  |
| `destination-channel` | **Yes**  | `latest/candidate` | Target channel in `track/risk` format.  |
| `base-name`           | **Yes**  | `ubuntu`           | Charmcraft base OS name.                |
| `base-channel`        | **Yes**  | `20.04`            | Charmcraft base OS version.             |
| `base-architecture`   | **Yes**  | `amd64`            | Charmcraft base architecture.           |
| `charm-path`          | No       | `.`                | Path to charm directory.                |
| `charmcraft-channel`  | No       | `latest/edge`      | Snap channel for Charmcraft.            |
| `tag-prefix`          | No       | —                  | Tag prefix for multi-charm repos.       |

**Outputs:** None

**Minimal usage example:**

```yaml
name: Release charm to channel

on:
  workflow_dispatch:
    inputs:
      origin-channel:
        description: "Origin channel"
        required: true
        default: "latest/edge"
      destination-channel:
        description: "Destination channel"
        required: true
        default: "latest/candidate"
      base-architecture:
        description: "Architecture (amd64, arm64, ...)"
        required: true
        default: "amd64"

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Release charm
        uses: canonical/charming-actions/release-charm@main
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          origin-channel: ${{ github.event.inputs.origin-channel }}
          destination-channel: ${{ github.event.inputs.destination-channel }}
          base-name: ubuntu
          base-channel: "22.04"
          base-architecture: ${{ github.event.inputs.base-architecture }}
```

> **Difference from `promote-charm`:** `release-charm` handles one base+arch at a time and updates GitHub release metadata; `promote-charm` bulk-promotes all bases/architectures automatically.

---

### 2.5 check-libraries

**`uses:` path:** `canonical/charming-actions/check-libraries@2.6.0`

Checks whether the charm libraries vendored in the repo are in sync with their published Charmhub counterparts. Adds PR labels and optionally comments or fails the build on drift.

**Inputs:**

| Input                | Required | Default                  | Description                                    |
| -------------------- | -------- | ------------------------ | ---------------------------------------------- |
| `credentials`        | **Yes**  | —                        | Charmhub credentials.                          |
| `github-token`       | **Yes**  | —                        | GitHub token for posting labels/comments.      |
| `charm-path`         | No       | `.`                      | Path to the charm directory.                   |
| `charmcraft-channel` | No       | `latest/stable`          | Snap channel for Charmcraft.                   |
| `use-labels`         | No       | `true`                   | Add PR labels indicating sync status.          |
| `label-success`      | No       | `Libraries: OK`          | Label text when libraries are in sync.         |
| `label-fail`         | No       | `Libraries: Out of sync` | Label text when libraries are out of sync.     |
| `comment-on-pr`      | No       | `false`                  | Post a warning comment when drift is detected. |
| `fail-build`         | No       | `false`                  | Fail the job when drift is detected.           |

**Outputs:** None

**Minimal usage example:**

```yaml
- name: Check charm libraries
  uses: canonical/charming-actions/check-libraries@2.6.0
  with:
    credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

### 2.6 release-libraries

**`uses:` path:** `canonical/charming-actions/release-libraries@2.6.0`

Publishes bumped charm libraries to Charmhub when their `LIBPATCH`/`LIBAPI` version has been incremented in the source. Run on push to main branches.

**Inputs:**

| Input                | Required | Default         | Description                                          |
| -------------------- | -------- | --------------- | ---------------------------------------------------- |
| `credentials`        | **Yes**  | —               | Charmhub credentials.                                |
| `github-token`       | **Yes**  | —               | GitHub token for tagging.                            |
| `charm-path`         | No       | `.`             | Path to the charm directory.                         |
| `charmcraft-channel` | No       | `latest/stable` | Snap channel for Charmcraft.                         |
| `fail-build`         | No       | `true`          | Whether to fail the job if library publishing fails. |

**Outputs:** None

**Minimal usage example:**

```yaml
- name: Release bumped libraries
  uses: canonical/charming-actions/release-libraries@2.6.0
  with:
    credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

### 2.7 upload-bundle

**`uses:` path:** `canonical/charming-actions/upload-bundle@2.6.0`

Uploads a Juju bundle to Charmhub.

**Inputs:**

| Input                | Required | Default         | Description                                            |
| -------------------- | -------- | --------------- | ------------------------------------------------------ |
| `credentials`        | **Yes**  | —               | Charmhub credentials.                                  |
| `github-token`       | **Yes**  | —               | GitHub token.                                          |
| `bundle-path`        | No       | `.`             | Path to the bundle directory containing `bundle.yaml`. |
| `channel`            | No       | `latest/edge`   | Charmhub channel to publish to.                        |
| `tag-prefix`         | No       | —               | Tag prefix (currently a no-op for bundles).            |
| `charmcraft-channel` | No       | `latest/stable` | Snap channel for Charmcraft.                           |

**Outputs:** None

**Minimal usage example:**

```yaml
- name: Upload bundle
  uses: canonical/charming-actions/upload-bundle@2.6.0
  with:
    credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
    github-token: ${{ secrets.GITHUB_TOKEN }}
    channel: "latest/edge"
```

---

### 2.8 dump-logs

**`uses:` path:** `canonical/charming-actions/dump-logs@2.6.0`

Dumps Juju debug logs, Kubernetes pod logs, deployments, replicasets, and node info for post-mortem debugging after integration test failures. Also uploads Charmcraft build logs as a GitHub Actions artifact (`charmcraft-logs`). Has no inputs.

**Inputs:** None
**Outputs:** None (uploads artifact `charmcraft-logs` with `~/.local/state/charmcraft/log/*.log`)

**Minimal usage example:**

```yaml
- name: Dump logs on failure
  if: failure()
  uses: canonical/charming-actions/dump-logs@2.6.0
```

---

### 2.9 get-charm-paths

**`uses:` path:** `canonical/charming-actions/get-charm-paths@2.6.0`

Scans the repository and emits a JSON array of relative paths to all charm directories (directories containing a `charmcraft.yaml`). Useful for dynamic matrix builds in monorepos.

**Inputs:** None

**Outputs:**

| Output        | Description                                                                        |
| ------------- | ---------------------------------------------------------------------------------- |
| `charm-paths` | JSON array string of relative paths (e.g. `["charms/myapp", "charms/myapp-k8s"]`). |

**Minimal usage example:**

```yaml
jobs:
  find-charms:
    runs-on: ubuntu-latest
    outputs:
      charm-paths: ${{ steps.get-paths.outputs.charm-paths }}
    steps:
      - uses: actions/checkout@v4
      - id: get-paths
        uses: canonical/charming-actions/get-charm-paths@2.6.0

  build:
    needs: find-charms
    runs-on: ubuntu-latest
    strategy:
      matrix:
        charm-path: ${{ fromJSON(needs.find-charms.outputs.charm-paths) }}
    steps:
      - uses: actions/checkout@v4
      - name: Pack ${{ matrix.charm-path }}
        uses: canonical/craft-actions/charmcraft/pack@main
        with:
          path: ${{ matrix.charm-path }}
```

---

## 3. Full Workflow Patterns

### Pattern A: PR workflow — build, test, upload to edge

```yaml
name: CI

on:
  pull_request:
    branches: [main, "track/*"]
  push:
    branches: [main, "track/*"]

jobs:
  build-and-upload:
    name: Build and upload to Charmhub edge
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # 1. Check charm library drift on PRs
      - name: Check charm libraries
        if: github.event_name == 'pull_request'
        uses: canonical/charming-actions/check-libraries@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          github-token: ${{ secrets.GITHUB_TOKEN }}

      # 2. Pack the charm
      - name: Pack charm
        id: pack
        uses: canonical/craft-actions/charmcraft/pack@main

      # 3. Determine the target channel from git context
      - name: Select Charmhub channel
        id: channel
        uses: canonical/charming-actions/channel@2.6.0

      # 4. Upload to Charmhub
      - name: Upload charm
        uses: canonical/charming-actions/upload-charm@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          channel: ${{ steps.channel.outputs.name }}
          built-charm-path: ${{ steps.pack.outputs.charms }}
          upload-image: "true"
```

### Pattern B: Push to main — release libraries + upload charm

```yaml
name: Release

on:
  push:
    branches: [main]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # 1. Publish any bumped charm libs
      - name: Release bumped charm libraries
        uses: canonical/charming-actions/release-libraries@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          github-token: ${{ secrets.GITHUB_TOKEN }}

      # 2. Calculate channel (main → latest/edge)
      - name: Select Charmhub channel
        id: channel
        uses: canonical/charming-actions/channel@2.6.0

      # 3. Pack
      - name: Pack charm
        id: pack
        uses: canonical/craft-actions/charmcraft/pack@main

      # 4. Upload
      - name: Upload charm
        uses: canonical/charming-actions/upload-charm@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          channel: ${{ steps.channel.outputs.name }}
          built-charm-path: ${{ steps.pack.outputs.charms }}
```

### Pattern C: Integration tests with log dumping

```yaml
name: Integration Tests

on:
  push:
    branches: [main]

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # 1. Pack charm
      - name: Pack charm
        id: pack
        uses: canonical/craft-actions/charmcraft/pack@main

      # 2. Run integration tests (example using tox/pytest-operator)
      - name: Run integration tests
        run: |
          tox -e integration -- \
            --model testing \
            --charm-path="${{ steps.pack.outputs.charms }}"
        env:
          JUJU_CONTROLLER: localhost

      # 3. Always dump logs on failure
      - name: Dump Juju and k8s debug logs
        if: failure()
        uses: canonical/charming-actions/dump-logs@2.6.0
```

### Pattern D: Promote from candidate → stable (manual dispatch)

```yaml
name: Promote to stable

on:
  workflow_dispatch:
    inputs:
      origin-channel:
        description: "Origin channel (e.g. 2.0/candidate)"
        required: true
        default: "latest/candidate"
      destination-channel:
        description: "Destination channel (e.g. 2.0/stable)"
        required: true
        default: "latest/stable"

jobs:
  promote:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Promote charm across all bases/architectures
        uses: canonical/charming-actions/promote-charm@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          origin-channel: ${{ github.event.inputs.origin-channel }}
          destination-channel: ${{ github.event.inputs.destination-channel }}
```

### Pattern E: Full pipeline — build → integration test → upload → promote

```yaml
name: Full C D Pipeline

on:
  push:
    branches: [main, "track/*"]

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      charm-files: ${{ steps.pack.outputs.charms }}
      channel: ${{ steps.channel.outputs.name }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Pack charm
        id: pack
        uses: canonical/craft-actions/charmcraft/pack@main
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: charm-files
          path: "*.charm"
      - name: Select channel
        id: channel
        uses: canonical/charming-actions/channel@2.6.0

  integration-test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: charm-files
      - name: Run integration tests
        run: tox -e integration
      - name: Dump logs on failure
        if: failure()
        uses: canonical/charming-actions/dump-logs@2.6.0

  upload-to-edge:
    needs: [build, integration-test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/download-artifact@v4
        with:
          name: charm-files
      - name: Upload charm to Charmhub
        uses: canonical/charming-actions/upload-charm@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
          channel: ${{ needs.build.outputs.channel }}
          built-charm-path: ${{ needs.build.outputs.charm-files }}

  promote-to-candidate:
    needs: upload-to-edge
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Promote latest/edge → latest/candidate
        uses: canonical/charming-actions/promote-charm@2.6.0
        with:
          credentials: ${{ secrets.CHARMCRAFT_TOKEN }}
          origin-channel: "latest/edge"
          destination-channel: "latest/candidate"
```

---

## 4. References

### canonical/craft-actions

| Resource                       | URL                                                                                         | Description                                                                |
| ------------------------------ | ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Repository                     | https://github.com/canonical/craft-actions                                                  | Monorepo of GitHub Actions for Snapcraft, Rockcraft, and Charmcraft.       |
| `charmcraft/pack` action.yaml  | https://github.com/canonical/craft-actions/blob/main/charmcraft/pack/action.yaml            | Authoritative input/output definitions for the pack action.                |
| `charmcraft/pack` README       | https://github.com/canonical/craft-actions/blob/main/charmcraft/pack/README.md              | Documentation and usage examples for charmcraft/pack.                      |
| `charmcraft/setup` action.yaml | https://github.com/canonical/craft-actions/blob/main/charmcraft/setup/action.yaml           | Authoritative input/output definitions for the setup action.               |
| `charmcraft/setup` README      | https://github.com/canonical/craft-actions/blob/main/charmcraft/setup/README.md             | Documentation for charmcraft/setup.                                        |
| Test workflow                  | https://github.com/canonical/craft-actions/blob/main/.github/workflows/test-charmcraft.yaml | Official integration test workflow demonstrating setup + pack in a matrix. |

### canonical/charming-actions

| Resource                        | URL                                                                                   | Description                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Repository                      | https://github.com/canonical/charming-actions                                         | Collection of Actions for Juju charm release automation.                 |
| Main README                     | https://github.com/canonical/charming-actions/blob/main/README.md                     | Overview, prerequisites, and examples for the whole collection.          |
| `channel` action.yaml           | https://github.com/canonical/charming-actions/blob/main/channel/action.yaml           | Channel selection action definition.                                     |
| `channel` README                | https://github.com/canonical/charming-actions/blob/main/channel/README.md             | Branch-to-channel mapping table and usage.                               |
| `upload-charm` action.yaml      | https://github.com/canonical/charming-actions/blob/main/upload-charm/action.yaml      | Full input definitions for upload-charm.                                 |
| `upload-charm` README           | https://github.com/canonical/charming-actions/blob/main/upload-charm/README.md        | Full documentation for upload-charm including resource handling notes.   |
| `promote-charm` action.yaml     | https://github.com/canonical/charming-actions/blob/main/promote-charm/action.yaml     | Input definitions for promote-charm.                                     |
| `promote-charm` README          | https://github.com/canonical/charming-actions/blob/main/promote-charm/README.md       | Usage, limitations, and multi-charm repo pattern.                        |
| `release-charm` action.yaml     | https://github.com/canonical/charming-actions/blob/main/release-charm/action.yaml     | Input definitions for release-charm.                                     |
| `release-charm` README          | https://github.com/canonical/charming-actions/blob/main/release-charm/README.md       | Usage, base/arch selection, and multi-charm repo patterns.               |
| `check-libraries` action.yaml   | https://github.com/canonical/charming-actions/blob/main/check-libraries/action.yaml   | Input definitions for check-libraries.                                   |
| `release-libraries` action.yaml | https://github.com/canonical/charming-actions/blob/main/release-libraries/action.yaml | Input definitions for release-libraries.                                 |
| `upload-bundle` action.yaml     | https://github.com/canonical/charming-actions/blob/main/upload-bundle/action.yaml     | Input definitions for upload-bundle.                                     |
| `dump-logs` action.yaml         | https://github.com/canonical/charming-actions/blob/main/dump-logs/action.yml          | Composite action that dumps Juju + k8s logs and uploads Charmcraft logs. |
| `get-charm-paths` action.yml    | https://github.com/canonical/charming-actions/blob/main/get-charm-paths/action.yml    | Emits JSON list of charm paths for monorepo matrix builds.               |

### Related Juju/Charmcraft documentation

| Resource                   | URL                                                    | Description                                             |
| -------------------------- | ------------------------------------------------------ | ------------------------------------------------------- |
| Charmcraft remote env auth | https://juju.is/docs/sdk/remote-env-auth               | How to generate and export Charmhub credentials for CI. |
| Charmcraft docs            | https://documentation.ubuntu.com/charmcraft/en/latest/ | Official Charmcraft documentation.                      |
| Juju SDK                   | https://juju.is/docs/sdk                               | Juju charm SDK documentation.                           |
