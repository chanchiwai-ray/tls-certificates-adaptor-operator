# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for charm.py."""

import json
import logging

import ops
import ops.testing
import pytest
from charmlibs.interfaces.tls_certificates import (
    Certificate,
    CertificateSigningRequest,
    PrivateKey,
    TLSCertificatesRequiresV4,
)

from charm import TLSCertificateAdaptorCharm
from constants import (
    CHARM_PRIVATE_KEY_SECRET_LABEL,
    JUJU_SECRET_LABEL_PREFIX,
    OLD_INTERFACE_RELATION_NAME,
    UPSTREAM_RELATION_NAME,
)
from crypto import build_csr, csr_sha256_hex, generate_private_key
from tests.unit.conftest import sign_csr

# Pre-generate a stable key so that test secret labels are predictable.
_TEST_KEY_PEM = generate_private_key()

# Class-level access to ObjectEvents is not fully typed; suppress the mypy warning once.
_CERT_AVAILABLE_EVENT = TLSCertificatesRequiresV4.on.certificate_available  # type: ignore[arg-type]


@pytest.fixture()
def context() -> ops.testing.Context:
    """Return a Context for TLSCertificateAdaptorCharm."""
    return ops.testing.Context(charm_type=TLSCertificateAdaptorCharm)


@pytest.fixture()
def key_secret() -> ops.testing.Secret:
    """Pre-populated charm private key Juju Secret."""
    return ops.testing.Secret(
        label=CHARM_PRIVATE_KEY_SECRET_LABEL,
        owner="unit",
        tracked_content={"private-key": _TEST_KEY_PEM},
    )


def _cert_req(common_name: str, sans: list[str]) -> str:
    """Return a JSON cert_requests string for the old reactive interface."""
    return json.dumps([{"cert_type": "server", "common_name": common_name, "sans": sans}])


def _mapping_label(common_name: str, sans: list[str]) -> str:
    """Compute the expected secret label for a CSR mapping."""
    csr_pem = build_csr(_TEST_KEY_PEM, common_name, sans)
    return f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}"


class TestReconcileStatus:
    """Tests for unit status set by reconcile()."""

    def test_waiting_status_when_no_upstream_relation(self, context: ops.testing.Context):
        """
        arrange: No upstream TLS provider relation.
        act: Run install.
        assert: Unit status is WaitingStatus.
        """
        state_out = context.run(context.on.install(), ops.testing.State())
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")

    def test_active_status_when_upstream_relation_exists(self, context: ops.testing.Context):
        """
        arrange: An upstream TLS provider relation is active.
        act: Run install.
        assert: Unit status is ActiveStatus.
        """
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        state_in = ops.testing.State(relations={upstream_relation})
        state_out = context.run(context.on.install(), state_in)
        assert state_out.unit_status == ops.ActiveStatus()

    def test_waiting_status_on_config_changed_without_upstream(self, context: ops.testing.Context):
        """
        arrange: No upstream relation.
        act: Run config_changed.
        assert: Unit status is WaitingStatus.
        """
        state_out = context.run(context.on.config_changed(), ops.testing.State())
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")


class TestRelationEvents:
    """Tests for old-interface relation event handling."""

    def test_certificates_relation_changed_calls_reconcile(self, context: ops.testing.Context):
        """
        arrange: An old-interface relation with a cert request.
        act: Emit certificates_relation_changed.
        assert: reconcile() runs and sets WaitingStatus (no upstream relation present).
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        state_in = ops.testing.State(relations={old_relation})
        state_out = context.run(context.on.relation_changed(old_relation, remote_unit=0), state_in)
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")

    def test_certificates_relation_changed_active_with_upstream(
        self, context: ops.testing.Context
    ):
        """
        arrange: Both old-interface and upstream relations active.
        act: Emit certificates_relation_changed.
        assert: Unit status is ActiveStatus.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        state_in = ops.testing.State(relations={old_relation, upstream_relation})
        state_out = context.run(context.on.relation_changed(old_relation, remote_unit=0), state_in)
        assert state_out.unit_status == ops.ActiveStatus()

    def test_certificates_relation_broken_calls_reconcile(self, context: ops.testing.Context):
        """
        arrange: An old-interface relation that is being broken.
        act: Emit certificates_relation_broken.
        assert: reconcile() runs without error.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        state_in = ops.testing.State(relations={old_relation})
        state_out = context.run(context.on.relation_broken(old_relation), state_in)
        assert state_out.unit_status == ops.WaitingStatus("Waiting for upstream TLS provider")


class TestCertificatesRelationChangedCsrMapping:
    """Tests for CSR mapping logic in _on_certificates_relation_changed (PR 002)."""

    def test_new_request_stores_csr_mapping_secret(
        self, context: ops.testing.Context, key_secret: ops.testing.Secret
    ):
        """
        arrange: One old-interface requirer with a new server cert request.
        act: Fire certificates_relation_changed.
        assert: A CSR mapping secret is created with the correct content.
        """
        relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={
                0: {"cert_requests": _cert_req("keystone.internal", ["keystone.internal"])}
            },
        )
        state = ops.testing.State(relations={relation}, secrets={key_secret})

        out = context.run(context.on.relation_changed(relation=relation), state)

        expected_label = _mapping_label("keystone.internal", ["keystone.internal"])
        mapping_secrets = [s for s in out.secrets if s.label == expected_label]
        assert len(mapping_secrets) == 1
        content = mapping_secrets[0].latest_content
        assert content["requirer-unit"] == "keystone/0"
        assert content["relation-id"] == str(relation.id)
        assert content["private-key"] == _TEST_KEY_PEM

    def test_repeated_event_for_same_request_is_idempotent(
        self, context: ops.testing.Context, key_secret: ops.testing.Secret
    ):
        """
        arrange: A CSR mapping secret already exists for a cert request.
        act: Fire certificates_relation_changed again with identical data.
        assert: No new mapping secret is created (secret count unchanged).
        """
        csr_pem = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
        existing_mapping = ops.testing.Secret(
            label=f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}",
            owner="unit",
            tracked_content={
                "private-key": _TEST_KEY_PEM,
                "requirer-unit": "keystone/0",
                "relation-id": "5",
            },
        )
        relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={
                0: {"cert_requests": _cert_req("keystone.internal", ["keystone.internal"])}
            },
        )
        state = ops.testing.State(relations={relation}, secrets={key_secret, existing_mapping})

        out = context.run(context.on.relation_changed(relation=relation), state)

        assert len(out.secrets) == len(state.secrets)

    def test_two_requesters_each_get_their_own_mapping_secret(
        self, context: ops.testing.Context, key_secret: ops.testing.Secret
    ):
        """
        arrange: Two old-interface requirer units each with a distinct cert request.
        act: Fire certificates_relation_changed.
        assert: Two distinct CSR mapping secrets are created.
        """
        relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={
                0: {"cert_requests": _cert_req("keystone.internal", ["keystone.internal"])},
                1: {"cert_requests": _cert_req("nova.internal", ["nova.internal"])},
            },
        )
        state = ops.testing.State(relations={relation}, secrets={key_secret})

        out = context.run(context.on.relation_changed(relation=relation), state)

        expected_labels = {
            _mapping_label("keystone.internal", ["keystone.internal"]),
            _mapping_label("nova.internal", ["nova.internal"]),
        }
        created = {s.label for s in out.secrets if s.label in expected_labels}
        assert created == expected_labels


class TestCertificatesUpstreamRelationJoined:
    """Tests for _on_certificates_upstream_relation_joined (PR 002)."""

    def test_with_pending_csrs_sets_active_status(
        self, context: ops.testing.Context, key_secret: ops.testing.Secret
    ):
        """
        arrange: Upstream relation joins while a pending old-interface CSR mapping exists.
        act: Fire certificates_upstream_relation_joined.
        assert: Unit status is ActiveStatus.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={
                0: {"cert_requests": _cert_req("keystone.internal", ["keystone.internal"])}
            },
        )
        csr_pem = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
        existing_mapping = ops.testing.Secret(
            label=f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}",
            owner="unit",
            tracked_content={
                "private-key": _TEST_KEY_PEM,
                "requirer-unit": "keystone/0",
                "relation-id": str(old_relation.id),
            },
        )
        upstream_relation = ops.testing.Relation(
            endpoint=UPSTREAM_RELATION_NAME,
            remote_app_name="vault-k8s",
        )
        state = ops.testing.State(
            relations={old_relation, upstream_relation},
            secrets={key_secret, existing_mapping},
        )

        out = context.run(context.on.relation_joined(relation=upstream_relation), state)

        assert out.unit_status == ops.ActiveStatus()

    def test_with_no_pending_csrs_sets_active_status_no_new_secrets(
        self, context: ops.testing.Context, key_secret: ops.testing.Secret
    ):
        """
        arrange: Upstream relation joins with no old-interface requests present.
        act: Fire certificates_upstream_relation_joined.
        assert: Unit status is ActiveStatus and no new secrets are created.
        """
        upstream_relation = ops.testing.Relation(
            endpoint=UPSTREAM_RELATION_NAME,
            remote_app_name="vault-k8s",
        )
        state = ops.testing.State(
            relations={upstream_relation},
            secrets={key_secret},
        )

        out = context.run(context.on.relation_joined(relation=upstream_relation), state)

        assert out.unit_status == ops.ActiveStatus()
        assert len(out.secrets) == len(state.secrets)


class TestCertificateAvailableDelivery:
    """Tests for _on_certificate_available (PR 003)."""

    def _build_mapping_secret(
        self,
        csr_pem: str,
        old_relation_id: int,
        requirer_unit_name: str = "keystone/0",
    ) -> ops.testing.Secret:
        """Build a pre-populated CSR mapping secret for the given CSR."""
        label = f"{JUJU_SECRET_LABEL_PREFIX}{csr_sha256_hex(csr_pem)}"
        return ops.testing.Secret(
            label=label,
            owner="unit",
            tracked_content={
                "private-key": _TEST_KEY_PEM,
                "requirer-unit": requirer_unit_name,
                "relation-id": str(old_relation_id),
            },
        )

    def test_happy_path_delivers_cert_and_revokes_mapping(
        self,
        context: ops.testing.Context,
        key_secret: ops.testing.Secret,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
    ):
        """
        arrange: Old-interface relation, upstream relation, and a CSR mapping secret.
        act: Fire certificate_available with a signed cert.
        assert: Old-interface unit databag contains cert + key; mapping secret is revoked.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        csr_pem = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
        mapping_secret = self._build_mapping_secret(csr_pem, old_relation.id)
        cert = sign_csr(csr_pem, ca_certificate, ca_private_key)

        state_in = ops.testing.State(
            relations={old_relation, upstream_relation},
            secrets={key_secret, mapping_secret},
        )

        out = context.run(
            context.on.custom(
                _CERT_AVAILABLE_EVENT,
                certificate=cert,
                certificate_signing_request=CertificateSigningRequest.from_string(csr_pem),
                ca=ca_certificate,
                chain=[ca_certificate],
            ),
            state_in,
        )

        out_old_relation = out.get_relation(old_relation.id)
        assert out_old_relation is not None
        payload = json.loads(out_old_relation.local_unit_data["keystone_0.processed_requests"])
        assert payload[0]["cert"] == str(cert)
        assert payload[0]["key"] == _TEST_KEY_PEM
        assert payload[0]["ca"] == str(ca_certificate)
        assert payload[0]["common_name"] == "keystone.internal"
        assert payload[0]["cert_type"] == "server"

    def test_mapping_secret_revoked_after_delivery(
        self,
        context: ops.testing.Context,
        key_secret: ops.testing.Secret,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
    ):
        """
        arrange: A CSR mapping secret exists.
        act: Fire certificate_available for that CSR.
        assert: The mapping secret no longer appears in the output state.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        csr_pem = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
        mapping_secret = self._build_mapping_secret(csr_pem, old_relation.id)
        cert = sign_csr(csr_pem, ca_certificate, ca_private_key)

        state_in = ops.testing.State(
            relations={old_relation, upstream_relation},
            secrets={key_secret, mapping_secret},
        )

        out = context.run(
            context.on.custom(
                _CERT_AVAILABLE_EVENT,
                certificate=cert,
                certificate_signing_request=CertificateSigningRequest.from_string(csr_pem),
                ca=ca_certificate,
                chain=[ca_certificate],
            ),
            state_in,
        )

        mapping_labels = {s.label for s in out.secrets if s.label == mapping_secret.label}
        assert mapping_labels == set()

    def test_missing_mapping_secret_logs_error_and_skips(
        self,
        context: ops.testing.Context,
        key_secret: ops.testing.Secret,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
        caplog: pytest.LogCaptureFixture,
    ):
        """
        arrange: No CSR mapping secret in state.
        act: Fire certificate_available.
        assert: Charm does not raise; an ERROR is logged.
        """
        csr_pem = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
        cert = sign_csr(csr_pem, ca_certificate, ca_private_key)
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)

        state_in = ops.testing.State(
            relations={upstream_relation},
            secrets={key_secret},
        )

        with caplog.at_level(logging.ERROR):
            out = context.run(
                context.on.custom(
                    _CERT_AVAILABLE_EVENT,
                    certificate=cert,
                    certificate_signing_request=CertificateSigningRequest.from_string(csr_pem),
                    ca=ca_certificate,
                    chain=[ca_certificate],
                ),
                state_in,
            )

        assert any("No CSR mapping found" in r.message for r in caplog.records)
        assert len(out.secrets) == len(state_in.secrets)

    def test_stale_old_relation_revokes_mapping_and_logs_info(
        self,
        context: ops.testing.Context,
        key_secret: ops.testing.Secret,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
        caplog: pytest.LogCaptureFixture,
    ):
        """
        arrange: Mapping secret references a relation_id that no longer exists.
        act: Fire certificate_available.
        assert: INFO is logged; mapping secret is revoked; no exception raised.
        """
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        csr_pem = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
        mapping_secret = self._build_mapping_secret(csr_pem, old_relation_id=9999)
        cert = sign_csr(csr_pem, ca_certificate, ca_private_key)

        state_in = ops.testing.State(
            relations={upstream_relation},
            secrets={key_secret, mapping_secret},
        )

        with caplog.at_level(logging.INFO):
            out = context.run(
                context.on.custom(
                    _CERT_AVAILABLE_EVENT,
                    certificate=cert,
                    certificate_signing_request=CertificateSigningRequest.from_string(csr_pem),
                    ca=ca_certificate,
                    chain=[ca_certificate],
                ),
                state_in,
            )

        assert any("no longer exists" in r.message for r in caplog.records)
        mapping_labels = {s.label for s in out.secrets if s.label == mapping_secret.label}
        assert mapping_labels == set()
