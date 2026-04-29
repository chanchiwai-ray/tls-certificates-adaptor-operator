<!-- Remember to update this file for your charm -- replace tls-certificate-adaptor and chanchiwai-ray/tls-certificate-adaptor-operator with the appropriate text. -->

# Contributing

This document explains the processes and practices recommended for contributing enhancements to the tls-certificate-adaptor charm.

## Overview

- Generally, before developing enhancements to this charm, you should consider [opening an issue ](link to issues page)
  explaining your use case.
- Familiarizing yourself with the [Juju documentation](https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/)
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Once your pull request is approved, we squash and merge your pull request branch onto the `main` branch. This creates
  a linear Git commit history.

## Changelog

Please ensure that any new feature, fix, or significant change is documented by adding an entry to the
[CHANGELOG.md](link to changelog) file. Use the date of the contribution as the header for new entries.

To learn more about changelog best practices, visit [Keep a Changelog](https://keepachangelog.com/).

## Submissions

If you want to address an issue or a bug in this project, notify in advance the people involved to avoid confusion;
also, reference the issue or bug number when you submit the changes.

- [Fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks) our
  [GitHub repository](link to GitHub repository) and add the changes to your fork, properly structuring your commits,
  providing detailed commit messages and signing your commits.
- Make sure the updated project builds and runs without warnings or errors; this includes linting, documentation, code
  and tests.
- Submit the changes as a [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Your changes will be reviewed in due time; if approved, they will be eventually merged.

#### Verified signatures on commits

All commits in a pull request must have cryptographic (verified) signatures. To add signatures on your commits, follow
the [GitHub documentation](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

## Development

To make contributions to this charm, you'll need a working [development
setup](https://documentation.ubuntu.com/juju/latest/howto/manage-your-juju-deployment/set-up-your-juju-deployment-local-testing-and-development/).

The code for this charm can be downloaded as follows:

```
git clone https://github.com/chanchiwai-ray/tls-certificate-adaptor-operator
```

Make sure to install [`uv`](https://docs.astral.sh/uv/). For example, you can install `uv` on Ubuntu using:

```bash
sudo snap install astral-uv --classic
```

For other systems, follow the [`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Then install `tox` with its extensions, and install a range of Python versions:

```bash
uv python install
uv tool install tox --with tox-uv
uv tool update-shell
```

To create a development environment, run:

```bash
uv sync --all-groups
source .venv/bin/activate
```

### Test

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

- `tox`: Executes all of the basic checks and tests (`lint`, `unit`, `static`, and `coverage-report`).
- `tox -e fmt`: Runs formatting using `ruff`.
- `tox -e lint`: Runs a range of static code analysis to check the code.
- `tox -e static`: Runs other checks such as `bandit` for security issues.
- `tox -e lint-fix`: Runs auto-fixing for issues found by `ruff`.
- `tox -e unit`: Runs the unit tests.
- `tox -e integration`: Runs the integration tests.

### Build the rock (optional)

Use [Rockcraft](https://documentation.ubuntu.com/rockcraft/stable/) to create an OCI image for the tls-certificate-adaptor app,
and then upload the image to a MicroK8s registry, which stores OCI archives so they can be downloaded and deployed.

Enable the MicroK8s registry:

```bash
microk8s enable registry
```

The following commands pack the OCI image and push it into the MicroK8s registry:

```bash
cd <project_dir>
rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:<rock-name>.rock docker://localhost:32000/<app-name>:latest
```

### Build the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

### Deploy the charm

```bash
# Create a model
juju add-model charm-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm
juju deploy ./tls-certificate-adaptor.charm
```
