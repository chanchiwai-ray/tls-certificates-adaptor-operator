# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for old_tls_certificate module."""

import json
from unittest.mock import MagicMock

import ops
import ops.testing
import pytest

from charm import TLSCertificateAdaptorCharm
from constants import OLD_INTERFACE_RELATION_NAME


@pytest.fixture()
def context() -> ops.testing.Context:
    """Return a Context for TLSCertificateAdaptorCharm."""
    return ops.testing.Context(charm_type=TLSCertificateAdaptorCharm)


def _make_charm_for_get(relations: list[ops.Relation]) -> MagicMock:
    """Build a mock CharmBase whose old-interface relations are *relations*."""
    charm = MagicMock(spec=ops.CharmBase)
    charm.model.relations = {OLD_INTERFACE_RELATION_NAME: relations}
    return charm


def _make_relation(unit_name: str, databag: dict[str, str], relation_id: int = 1) -> ops.Relation:
    """Build a minimal mock ops.Relation for unit testing."""
    relation = MagicMock(spec=ops.Relation)
    relation.id = relation_id
    unit = MagicMock(spec=ops.Unit)
    unit.name = unit_name
    relation.units = {unit}
    relation.data = {unit: databag}
    return relation


class TestGetCertificateRequests:
    """Tests for OldTLSCertificatesRelation.get_certificate_requests()."""

    def test_valid_server_request(self):
        """
        arrange: One requirer unit with a valid server cert_request in its databag.
        act: Call get_certificate_requests.
        assert: Returns one CertificateRequest with the correct fields.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps(
            [
                {
                    "cert_type": "server",
                    "common_name": "keystone.internal",
                    "sans": ["keystone.internal"],
                }
            ]
        )
        relation = _make_relation(
            "keystone/0", {"cert_requests": cert_requests_data}, relation_id=5
        )
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm).get_certificate_requests()
        assert requests[0].common_name == "keystone.internal"
        assert requests[0].sans_dns == ["keystone.internal"]
        assert requests[0].cert_type == "server"
        assert requests[0].requirer_unit_name == "keystone/0"
        assert requests[0].relation_id == 5

    def test_non_server_cert_type_filtered(self):
        """
        arrange: One requirer unit with a client cert_request.
        act: Call get_certificate_requests.
        assert: Returns an empty list.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps(
            [{"cert_type": "client", "common_name": "keystone.internal", "sans": []}]
        )
        relation = _make_relation("keystone/0", {"cert_requests": cert_requests_data})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm).get_certificate_requests()

        assert requests == []

    def test_empty_databag_returns_empty_list(self):
        """
        arrange: One requirer unit with no cert_requests key.
        act: Call get_certificate_requests.
        assert: Returns an empty list.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation("keystone/0", {})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm).get_certificate_requests()

        assert requests == []

    def test_malformed_json_returns_empty_list(self):
        """
        arrange: One requirer unit with malformed JSON in cert_requests.
        act: Call get_certificate_requests.
        assert: Returns an empty list (no exception raised).
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation("keystone/0", {"cert_requests": "not-json"})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm).get_certificate_requests()

        assert requests == []


class TestWriteCertificate:
    """Tests for OldTLSCertificatesRelation.write_certificate()."""

    def _make_charm_for_write(self, relation_id: int = 1) -> tuple[MagicMock, dict]:
        """Build a mock charm whose get_relation returns a writable mock relation."""
        charm = MagicMock(spec=ops.CharmBase)
        local_databag: dict = {}
        relation = MagicMock(spec=ops.Relation)
        relation.id = relation_id
        relation.data = {charm.unit: local_databag}
        charm.model.get_relation.return_value = relation
        return charm, local_databag

    def test_writes_correct_databag_key_and_content(self):
        """
        arrange: A mock relation with an empty local unit databag.
        act: Call write_certificate for keystone/0.
        assert: The databag contains the correctly formatted key and value.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, local_databag = self._make_charm_for_write(relation_id=5)
        OldTLSCertificatesRelation(charm).write_certificate(
            relation_id=5,
            requirer_unit_name="keystone/0",
            common_name="keystone.internal",
            cert="CERT_PEM",
            key="KEY_PEM",
            ca="CA_PEM",
        )

        assert "keystone_0.processed_requests" in local_databag
        content = json.loads(local_databag["keystone_0.processed_requests"])
        assert len(content) == 1
        assert content[0]["cert_type"] == "server"
        assert content[0]["common_name"] == "keystone.internal"
        assert content[0]["cert"] == "CERT_PEM"
        assert content[0]["key"] == "KEY_PEM"
        assert content[0]["ca"] == "CA_PEM"

    def test_overwrites_existing_entry(self):
        """
        arrange: A databag already containing a processed_requests entry.
        act: Call write_certificate again for the same unit.
        assert: The entry is overwritten, not appended.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, local_databag = self._make_charm_for_write(relation_id=1)
        existing = json.dumps(
            [
                {
                    "cert_type": "server",
                    "common_name": "keystone.internal",
                    "cert": "OLD",
                    "key": "OLD",
                    "ca": "OLD",
                }
            ]
        )
        local_databag["keystone_0.processed_requests"] = existing

        OldTLSCertificatesRelation(charm).write_certificate(
            relation_id=1,
            requirer_unit_name="keystone/0",
            common_name="keystone.internal",
            cert="NEW_CERT",
            key="NEW_KEY",
            ca="NEW_CA",
        )

        content = json.loads(local_databag["keystone_0.processed_requests"])
        assert len(content) == 1
        assert content[0]["cert"] == "NEW_CERT"
