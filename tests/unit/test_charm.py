# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for charm.py."""

import json

import ops
import ops.testing
import pytest
from charmlibs.interfaces.tls_certificates import (
    Certificate,
    PrivateKey,
)

from charm import TLSCertificateAdaptorCharm
from constants import OLD_INTERFACE_RELATION_NAME, UPSTREAM_RELATION_NAME
from tests.unit.conftest import sign_csr

# A session-level key and CSR for tests that need a real cert.
_LIBRARY_KEY = PrivateKey.generate(key_size=2048)
# Secret label used by TLSCertificatesRequiresV4 for the unit-owned private key.
# Format: {LIBID}-private-key-{unit_number}-{relationship_name}
_LIBID = "afd8c2bccf834997afce12c2706d2ede"
_LIBRARY_KEY_SECRET_LABEL = f"{_LIBID}-private-key-0-{UPSTREAM_RELATION_NAME}"


def _library_key_secret() -> ops.testing.Secret:
    """Return a pre-seeded Juju Secret for the library's unit private key."""
    return ops.testing.Secret(
        {"private-key": str(_LIBRARY_KEY)},
        label=_LIBRARY_KEY_SECRET_LABEL,
        owner="unit",
    )


def _cert_req(common_name: str, sans: list[str]) -> str:
    """Return a JSON cert_requests string for the old reactive interface (batch dict format)."""
    return json.dumps({common_name: {"sans": sans}})


@pytest.fixture()
def context() -> ops.testing.Context:
    """Return a Context for TLSCertificateAdaptorCharm."""
    return ops.testing.Context(charm_type=TLSCertificateAdaptorCharm)


class TestReconcileStatus:
    """Tests for unit status set by reconcile()."""

    def test_blocked_status_when_no_upstream_relation(self, context: ops.testing.Context):
        """
        arrange: No upstream TLS provider relation.
        act: Run install.
        assert: Unit status is BlockedStatus.
        """
        state_out = context.run(context.on.install(), ops.testing.State())
        assert state_out.unit_status == ops.BlockedStatus("Missing upstream TLS provider relation")

    def test_active_status_when_both_relations_exist(self, context: ops.testing.Context):
        """
        arrange: Both old-interface and upstream TLS provider relations are active.
        act: Run install.
        assert: Unit status is ActiveStatus.
        """
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        old_relation = ops.testing.Relation(endpoint=OLD_INTERFACE_RELATION_NAME)
        state_in = ops.testing.State(relations={upstream_relation, old_relation})
        state_out = context.run(context.on.install(), state_in)
        assert state_out.unit_status == ops.ActiveStatus()

    def test_blocked_status_when_no_old_interface_relation(self, context: ops.testing.Context):
        """
        arrange: Upstream relation exists but no old-interface relation.
        act: Run install.
        assert: Unit status is BlockedStatus.
        """
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        state_in = ops.testing.State(relations={upstream_relation})
        state_out = context.run(context.on.install(), state_in)
        assert state_out.unit_status == ops.BlockedStatus("Missing old TLS interface relation")

    def test_blocked_status_on_config_changed_without_upstream(self, context: ops.testing.Context):
        """
        arrange: No upstream relation.
        act: Run config_changed.
        assert: Unit status is BlockedStatus.
        """
        state_out = context.run(context.on.config_changed(), ops.testing.State())
        assert state_out.unit_status == ops.BlockedStatus("Missing upstream TLS provider relation")


class TestRelationEvents:
    """Tests for old-interface relation event handling."""

    def test_certificates_relation_changed_blocked_without_upstream(
        self, context: ops.testing.Context
    ):
        """
        arrange: An old-interface relation but no upstream relation.
        act: Emit certificates_relation_changed.
        assert: Unit status is BlockedStatus.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        state_in = ops.testing.State(relations={old_relation})
        state_out = context.run(context.on.relation_changed(old_relation, remote_unit=0), state_in)
        assert state_out.unit_status == ops.BlockedStatus("Missing upstream TLS provider relation")

    def test_certificates_relation_changed_active_with_both_relations(
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
        assert: reconcile() runs (BlockedStatus because no upstream).
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        state_in = ops.testing.State(relations={old_relation})
        state_out = context.run(context.on.relation_broken(old_relation), state_in)
        assert state_out.unit_status == ops.BlockedStatus("Missing upstream TLS provider relation")

    def test_certificates_relation_broken_no_secrets_created_or_removed(
        self, context: ops.testing.Context
    ):
        """
        arrange: An old-interface relation broken with an upstream relation present.
        act: Emit certificates_relation_broken.
        assert: No charm-owned secrets are created or removed.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        state_in = ops.testing.State(relations={old_relation, upstream_relation})
        state_out = context.run(context.on.relation_broken(old_relation), state_in)
        # Library may create its own private-key secret; we just assert no extra charm secrets
        assert state_out.unit_status == ops.BlockedStatus("Missing old TLS interface relation")


class TestUpgradeCharm:
    """Tests for upgrade_charm event handled by reconcile."""

    def test_upgrade_charm_sets_active_status_when_both_relations_exist(
        self, context: ops.testing.Context
    ):
        """
        arrange: Both upstream TLS provider and old-interface relations are active.
        act: Fire upgrade_charm.
        assert: Unit status is ActiveStatus.
        """
        upstream_relation = ops.testing.Relation(endpoint=UPSTREAM_RELATION_NAME)
        old_relation = ops.testing.Relation(endpoint=OLD_INTERFACE_RELATION_NAME)
        state_in = ops.testing.State(relations={upstream_relation, old_relation})

        out = context.run(context.on.upgrade_charm(), state_in)

        assert out.unit_status == ops.ActiveStatus()

    def test_upgrade_charm_blocked_without_upstream(self, context: ops.testing.Context):
        """
        arrange: No upstream relation exists.
        act: Fire upgrade_charm.
        assert: Unit status is BlockedStatus.
        """
        out = context.run(context.on.upgrade_charm(), ops.testing.State())
        assert out.unit_status == ops.BlockedStatus("Missing upstream TLS provider relation")


class TestCertificatesUpstreamRelationChanged:
    """Tests for upstream relation_changed (triggers reconcile and cert delivery)."""

    def test_upstream_relation_changed_with_old_relation_sets_active(
        self, context: ops.testing.Context
    ):
        """
        arrange: Old-interface relation exists; upstream relation fires relation_changed.
        act: Fire certificates_upstream_relation_changed.
        assert: Unit status is ActiveStatus.
        """
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
        )
        upstream_relation = ops.testing.Relation(
            endpoint=UPSTREAM_RELATION_NAME,
            remote_app_name="vault-k8s",
        )
        state = ops.testing.State(relations={old_relation, upstream_relation})

        out = context.run(context.on.relation_changed(relation=upstream_relation), state)

        assert out.unit_status == ops.ActiveStatus()

    def test_upstream_relation_changed_delivers_cert_to_old_interface(
        self,
        context: ops.testing.Context,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
    ):
        """
        arrange: Upstream relation app databag contains an issued cert; old-interface
                 relation has a pending request.
        act: Fire certificates_upstream_relation_changed.
        assert: The cert and key are written to the old-interface relation databag.
        """
        from charmlibs.interfaces.tls_certificates import CertificateRequestAttributes

        attrs = CertificateRequestAttributes(
            common_name="keystone.internal",
            sans_dns=["keystone.internal"],
            add_unique_id_to_subject_name=False,
        )
        csr = attrs.generate_csr(_LIBRARY_KEY)
        cert = sign_csr(str(csr), ca_certificate, ca_private_key)

        upstream_relation = ops.testing.Relation(
            endpoint=UPSTREAM_RELATION_NAME,
            remote_app_data={
                "certificates": json.dumps(
                    [
                        {
                            "ca": str(ca_certificate),
                            "certificate_signing_request": str(csr),
                            "certificate": str(cert),
                            "chain": None,
                        }
                    ]
                ),
            },
        )
        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={
                0: {"cert_requests": _cert_req("keystone.internal", ["keystone.internal"])}
            },
        )
        state_in = ops.testing.State(
            relations={upstream_relation, old_relation},
            secrets={_library_key_secret()},
        )

        out = context.run(context.on.relation_changed(relation=upstream_relation), state_in)

        assert out.unit_status == ops.ActiveStatus()
        out_old_rel = out.get_relation(old_relation.id)
        assert out_old_rel is not None
        payload_raw = out_old_rel.local_unit_data.get("keystone_0.processed_requests", "")
        assert payload_raw, "processed_requests should be written on upstream relation_changed"
        payload = json.loads(payload_raw)
        assert "keystone.internal" in payload
        assert "cert" in payload["keystone.internal"]
        assert "key" in payload["keystone.internal"]


class TestCertificateDelivery:
    """Tests for certificate delivery via reconcile on upstream relation_changed."""

    def _upstream_relation_with_cert(
        self, csr: object, cert: object, ca_certificate: object
    ) -> ops.testing.Relation:
        """Return an upstream relation with the given cert in its app databag."""
        return ops.testing.Relation(
            endpoint=UPSTREAM_RELATION_NAME,
            remote_app_data={
                "certificates": json.dumps(
                    [
                        {
                            "ca": str(ca_certificate),
                            "certificate_signing_request": str(csr),
                            "certificate": str(cert),
                            "chain": None,
                        }
                    ]
                ),
            },
        )

    def test_happy_path_delivers_cert_batch_format(
        self,
        context: ops.testing.Context,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
    ):
        """
        arrange: Old-interface relation with a pending batch cert request; upstream has cert.
        act: Fire upstream relation_changed.
        assert: processed_requests dict contains cert and key; ca is top-level; ActiveStatus set.
        """
        from charmlibs.interfaces.tls_certificates import CertificateRequestAttributes

        attrs = CertificateRequestAttributes(
            common_name="keystone.internal",
            sans_dns=["keystone.internal"],
            add_unique_id_to_subject_name=False,
        )
        csr = attrs.generate_csr(_LIBRARY_KEY)
        cert = sign_csr(str(csr), ca_certificate, ca_private_key)

        old_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={
                0: {"cert_requests": _cert_req("keystone.internal", ["keystone.internal"])}
            },
        )
        upstream_relation = self._upstream_relation_with_cert(csr, cert, ca_certificate)
        state_in = ops.testing.State(
            relations={old_relation, upstream_relation},
            secrets={_library_key_secret()},
        )

        out = context.run(context.on.relation_changed(relation=upstream_relation), state_in)

        assert out.unit_status == ops.ActiveStatus()
        out_old_relation = out.get_relation(old_relation.id)
        assert out_old_relation is not None
        payload_raw = out_old_relation.local_unit_data.get("keystone_0.processed_requests", "")
        assert payload_raw, "processed_requests key should be written"
        payload = json.loads(payload_raw)
        assert "keystone.internal" in payload
        assert "cert" in payload["keystone.internal"]
        assert "key" in payload["keystone.internal"]
        assert "ca" in out_old_relation.local_unit_data

    def test_ca_propagated_to_all_old_interface_relations(
        self,
        context: ops.testing.Context,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
    ):
        """
        arrange: Two old-interface relations; upstream has issued a cert for one.
        act: Fire upstream relation_changed.
        assert: ca key is written to BOTH old-interface relation databags.
        """
        from charmlibs.interfaces.tls_certificates import CertificateRequestAttributes

        attrs = CertificateRequestAttributes(
            common_name="keystone.internal",
            sans_dns=["keystone.internal"],
            add_unique_id_to_subject_name=False,
        )
        csr = attrs.generate_csr(_LIBRARY_KEY)
        cert = sign_csr(str(csr), ca_certificate, ca_private_key)

        keystone_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="keystone",
            remote_units_data={
                0: {"cert_requests": _cert_req("keystone.internal", ["keystone.internal"])}
            },
        )
        cinder_relation = ops.testing.Relation(
            endpoint=OLD_INTERFACE_RELATION_NAME,
            remote_app_name="cinder",
        )
        upstream_relation = self._upstream_relation_with_cert(csr, cert, ca_certificate)
        state_in = ops.testing.State(
            relations={keystone_relation, cinder_relation, upstream_relation},
            secrets={_library_key_secret()},
        )

        out = context.run(context.on.relation_changed(relation=upstream_relation), state_in)

        for rel_id in (keystone_relation.id, cinder_relation.id):
            out_rel = out.get_relation(rel_id)
            assert out_rel is not None
            assert out_rel.local_unit_data.get("ca") == str(ca_certificate)


class TestReconcileCaBundle:
    """Tests for CA bundle written during reconcile()."""

    def test_config_changed_writes_ca_when_upstream_has_issued_certs(
        self,
        context: ops.testing.Context,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
    ):
        """
        arrange: Upstream relation app databag contains an issued certificate.
        act: Run config_changed.
        assert: The CA cert is written to the old-interface relation local unit databag.
        """
        from charmlibs.interfaces.tls_certificates import CertificateRequestAttributes

        attrs = CertificateRequestAttributes(
            common_name="keystone.internal",
            sans_dns=["keystone.internal"],
            add_unique_id_to_subject_name=False,
        )
        csr = attrs.generate_csr(_LIBRARY_KEY)
        cert = sign_csr(str(csr), ca_certificate, ca_private_key)

        upstream_relation = ops.testing.Relation(
            endpoint=UPSTREAM_RELATION_NAME,
            remote_app_data={
                "certificates": json.dumps(
                    [
                        {
                            "ca": str(ca_certificate),
                            "certificate_signing_request": str(csr),
                            "certificate": str(cert),
                            "chain": None,
                        }
                    ]
                ),
            },
        )
        old_relation = ops.testing.Relation(endpoint=OLD_INTERFACE_RELATION_NAME)
        state = ops.testing.State(
            relations={upstream_relation, old_relation},
            secrets={_library_key_secret()},
        )

        out = context.run(context.on.config_changed(), state)

        out_old_rel = out.get_relation(old_relation.id)
        assert out_old_rel is not None
        assert str(ca_certificate) in out_old_rel.local_unit_data.get("ca", "")

    def test_extra_ca_from_config_appended_to_bundle(
        self,
        context: ops.testing.Context,
        ca_certificate: Certificate,
        ca_private_key: PrivateKey,
        intermediate_ca_certificate: Certificate,
    ):
        """
        arrange: ca-certificates config contains an additional CA.
        act: Run config_changed with upstream having issued certs.
        assert: Both event.ca and config CA appear in the written 'ca' bundle.
        """
        from charmlibs.interfaces.tls_certificates import CertificateRequestAttributes

        attrs = CertificateRequestAttributes(
            common_name="keystone.internal",
            sans_dns=["keystone.internal"],
            add_unique_id_to_subject_name=False,
        )
        csr = attrs.generate_csr(_LIBRARY_KEY)
        cert = sign_csr(str(csr), ca_certificate, ca_private_key)

        upstream_relation = ops.testing.Relation(
            endpoint=UPSTREAM_RELATION_NAME,
            remote_app_data={
                "certificates": json.dumps(
                    [
                        {
                            "ca": str(ca_certificate),
                            "certificate_signing_request": str(csr),
                            "certificate": str(cert),
                            "chain": None,
                        }
                    ]
                ),
            },
        )
        old_relation = ops.testing.Relation(endpoint=OLD_INTERFACE_RELATION_NAME)
        state = ops.testing.State(
            relations={upstream_relation, old_relation},
            config={"ca-certificates": str(intermediate_ca_certificate)},
            secrets={_library_key_secret()},
        )

        out = context.run(context.on.config_changed(), state)

        out_old_rel = out.get_relation(old_relation.id)
        assert out_old_rel is not None
        ca_bundle = out_old_rel.local_unit_data.get("ca", "")
        assert str(ca_certificate) in ca_bundle
        assert str(intermediate_ca_certificate) in ca_bundle
