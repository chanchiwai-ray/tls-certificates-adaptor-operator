#!/usr/bin/env python3

# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Integration tests."""

import json
import logging
import os
import time

import jubilant

logger = logging.getLogger(__name__)

SELF_SIGNED_CERTIFICATES = "self-signed-certificates"
ADAPTOR_APP = "tls-certificates-adaptor"
KEYSTONE_APP = "keystone"
MYSQL_APP = "mysql"


def _local_charm_path(charm: str) -> str:
    """Ensure the charm path is treated as a local file by juju deploy."""
    if not charm.startswith((".", "/")):
        charm = os.path.join(".", charm)
    return charm


def _all_settled(status: jubilant.Status) -> bool:
    """Return True when all apps have units with running agents and settled workload status."""
    for app_name in (SELF_SIGNED_CERTIFICATES, ADAPTOR_APP, KEYSTONE_APP, MYSQL_APP):
        app = status.apps.get(app_name)
        if not app or not app.units:
            return False
        for unit in app.units.values():
            if unit.juju_status.current in ("allocating", "pending", "lost", "unknown"):
                return False
            if unit.workload_status.current not in ("active", "blocked", "waiting"):
                return False
    return True


def _show_unit(juju: jubilant.Juju, app: str) -> dict:
    """Run show-unit and return parsed JSON, raising with context on failure."""
    raw = juju.cli("show-unit", "--format", "json", f"{app}/0")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse show-unit output for %s: %s", app, raw[:500])
        raise


def _wait_for_upstream_cert(juju: jubilant.Juju, timeout: int = 300) -> dict | None:
    """Poll the adaptor until certificates appear in the upstream relation app data."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        unit_data = _show_unit(juju, ADAPTOR_APP)
        unit_info = unit_data.get(f"{ADAPTOR_APP}/0", {})
        for rel in unit_info.get("relation-info", []):
            if rel.get("endpoint") == "certificates-upstream":
                app_data = rel.get("application-data", {})
                if app_data.get("certificates"):
                    return app_data
        time.sleep(5)
    return None


def _wait_for_old_interface_cert(juju: jubilant.Juju, timeout: int = 600) -> str | None:
    """Poll keystone until the adaptor's ca cert appears in the certificates relation."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        unit_data = _show_unit(juju, KEYSTONE_APP)
        unit_info = unit_data.get(f"{KEYSTONE_APP}/0", {})
        for rel in unit_info.get("relation-info", []):
            if rel.get("endpoint") == "certificates":
                for related in rel.get("related-units", {}).values():
                    ca = (related.get("data") or {}).get("ca")
                    if ca:
                        return ca
        time.sleep(5)
    return None


def test_certificate_bridging(juju: jubilant.Juju, charm: str):
    """Validate the adaptor bridges v4 TLS certs from upstream to old v1 requirers.

    Deploys self-signed-certificates (v4 provider), the adaptor (bridge),
    keystone (old v1 requirer), and mysql (keystone's database). Integrates
    all charms and verifies that certificates flow from the v4 provider,
    through the adaptor, and appear in the old v1 relation data.

    arrange: Deploy self-signed-certificates, adaptor, mysql, keystone.
    act: Integrate all four charms together.
    assert: Certificate data exists in both the upstream and old-interface
        relation databags, and all charms reach expected states.
    """
    juju.deploy(SELF_SIGNED_CERTIFICATES, channel="latest/edge")

    juju.deploy(MYSQL_APP, channel="8.0/stable")

    juju.deploy(KEYSTONE_APP, channel="yoga/stable")

    juju.deploy(_local_charm_path(charm))

    juju.wait(_all_settled, timeout=600)

    juju.integrate(f"{KEYSTONE_APP}:shared-db", f"{MYSQL_APP}:shared-db")

    juju.integrate(
        f"{KEYSTONE_APP}:certificates",
        f"{ADAPTOR_APP}:certificates",
    )

    juju.integrate(
        f"{ADAPTOR_APP}:certificates-upstream",
        SELF_SIGNED_CERTIFICATES,
    )

    juju.wait(_all_settled, timeout=1200)

    upstream_cert_data = _wait_for_upstream_cert(juju, timeout=300)
    assert upstream_cert_data, (
        "No certificates found in certificates-upstream app data; "
        "self-signed-certificates did not issue any certificates."
    )
    assert "certificates" in upstream_cert_data
    logger.info("Upstream certs found: %d bytes", len(upstream_cert_data["certificates"]))

    ca_cert = _wait_for_old_interface_cert(juju, timeout=600)
    assert ca_cert, (
        "No CA certificate found in keystone:certificates relation data. "
        "The adaptor did not deliver certificates to keystone."
    )
    assert ca_cert.startswith("-----BEGIN CERTIFICATE-----")
    logger.info("Old-interface CA cert delivered to keystone (%d bytes)", len(ca_cert))

    status = juju.status()

    adaptor = status.apps[ADAPTOR_APP]
    unit = next(iter(adaptor.units.values()))
    assert unit.workload_status.current == "active", (
        f"Adaptor should be active, got {unit.workload_status.current}: "
        f"{unit.workload_status.message}"
    )

    ssc = status.apps[SELF_SIGNED_CERTIFICATES]
    assert ssc.is_active, f"self-signed-certificates is not active: {ssc.app_status.current}"
