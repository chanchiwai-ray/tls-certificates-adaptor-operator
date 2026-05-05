# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for old_tls_certificate module."""

import json
from unittest.mock import MagicMock

import ops

from constants import OLD_INTERFACE_RELATION_NAME


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

    def test_batch_format(self):
        """
        arrange: One requirer unit with cert_requests as a JSON dict (batch format).
        act: Call get_certificate_requests.
        assert: Returns one CertificateRequest with is_legacy=False.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps({"keystone.internal": {"sans": ["keystone.internal"]}})
        relation = _make_relation(
            "keystone/0", {"cert_requests": cert_requests_data}, relation_id=5
        )
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert len(requests) == 2
        server_req = next(r for r in requests if not r.is_client)
        assert server_req.common_name == "keystone.internal"
        assert server_req.sans == ["keystone.internal"]
        assert server_req.cert_type == "server"
        assert server_req.requirer_unit_name == "keystone/0"
        assert server_req.relation_id == 5
        assert server_req.is_legacy is False
        client_req = next(r for r in requests if r.is_client)
        assert client_req.common_name == "keystone-client"
        assert client_req.cert_type == "client"
        assert client_req.relation_id == 5

    def test_batch_format_multiple_cns(self):
        """
        arrange: One requirer unit with two CNs in the batch dict.
        act: Call get_certificate_requests.
        assert: Returns two CertificateRequest objects, both with is_legacy=False.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps(
            {
                "keystone.internal": {"sans": ["10.0.0.1"]},
                "nova.internal": {"sans": ["10.0.0.2"]},
            }
        )
        relation = _make_relation("keystone/0", {"cert_requests": cert_requests_data})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert len(requests) == 3
        server_reqs = [r for r in requests if not r.is_client]
        client_reqs = [r for r in requests if r.is_client]
        cns = {r.common_name for r in server_reqs}
        assert cns == {"keystone.internal", "nova.internal"}
        assert all(r.is_legacy is False for r in server_reqs)
        assert len(client_reqs) == 1
        assert client_reqs[0].common_name == "keystone-client"

    def test_legacy_format(self):
        """
        arrange: One requirer unit with common_name as a direct databag key (legacy format).
        act: Call get_certificate_requests.
        assert: Returns one CertificateRequest with is_legacy=True.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation(
            "cinder/0",
            {
                "common_name": "cinder.internal",
                "sans": '["10.149.56.105"]',
            },
        )
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert len(requests) == 2
        server_req = next(r for r in requests if not r.is_client)
        assert server_req.common_name == "cinder.internal"
        assert server_req.sans == ["10.149.56.105"]
        assert server_req.is_legacy is True
        client_req = next(r for r in requests if r.is_client)
        assert client_req.common_name == "cinder-client"

    def test_both_formats_in_same_databag(self):
        """
        arrange: Unit databag has both common_name (legacy) and cert_requests (batch).
        act: Call get_certificate_requests.
        assert: Returns two requests: one is_legacy=True, one is_legacy=False.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation(
            "keystone/0",
            {
                "common_name": "cn1.internal",
                "sans": '["10.0.0.1"]',
                "cert_requests": json.dumps({"cn2.internal": {"sans": ["10.0.0.2"]}}),
            },
        )
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert len(requests) == 3
        server_reqs = [r for r in requests if not r.is_client]
        client_reqs = [r for r in requests if r.is_client]
        legacy = next(r for r in server_reqs if r.is_legacy)
        batch = next(r for r in server_reqs if not r.is_legacy)
        assert legacy.common_name == "cn1.internal"
        assert batch.common_name == "cn2.internal"
        assert len(client_reqs) == 1
        assert client_reqs[0].common_name == "keystone-client"

    def test_missing_cert_requests_no_common_name(self):
        """
        arrange: One requirer unit with no cert_requests key and no common_name key.
        act: Call get_certificate_requests.
        assert: Returns an empty list.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation("keystone/0", {})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert requests == []

    def test_malformed_cert_requests_not_json(self):
        """
        arrange: One requirer unit with malformed JSON in cert_requests.
        act: Call get_certificate_requests.
        assert: Returns an empty list; no exception raised.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation("keystone/0", {"cert_requests": "not-json"})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert requests == []

    def test_cert_requests_not_dict(self):
        """
        arrange: cert_requests is a JSON list (old wrong format).
        act: Call get_certificate_requests.
        assert: Returns an empty list; warning logged.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps([{"cert_type": "server", "common_name": "cn"}])
        relation = _make_relation("keystone/0", {"cert_requests": cert_requests_data})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert requests == []

    def test_legacy_malformed_sans(self):
        """
        arrange: Legacy databag with common_name set but sans is not valid JSON.
        act: Call get_certificate_requests.
        assert: Returns one CertificateRequest with sans=[] and is_legacy=True.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation(
            "keystone/0", {"common_name": "cn1.internal", "sans": "not-json"}
        )
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert len(requests) == 2
        server_req = next(r for r in requests if not r.is_client)
        assert server_req.common_name == "cn1.internal"
        assert server_req.sans == []
        assert server_req.is_legacy is True
        client_req = next(r for r in requests if r.is_client)
        assert client_req.common_name == "keystone-client"

    def test_batch_sans_not_list(self):
        """
        arrange: Batch dict where sans is a plain string, not a list.
        act: Call get_certificate_requests.
        assert: Returns one request with sans wrapping the string in a list.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps({"cn1.internal": {"sans": "10.0.0.1"}})
        relation = _make_relation("keystone/0", {"cert_requests": cert_requests_data})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert len(requests) == 2
        server_req = next(r for r in requests if not r.is_client)
        assert server_req.sans == ["10.0.0.1"]
        assert server_req.is_legacy is False
        client_req = next(r for r in requests if r.is_client)
        assert client_req.common_name == "keystone-client"


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

    def test_write_certificate_batch(self):
        """
        arrange: A mock relation with an empty local unit databag.
        act: Call write_certificate with is_legacy=False.
        assert: {munged}.processed_requests dict contains the cert/key, and ca is top-level.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, local_databag = self._make_charm_for_write(relation_id=5)
        OldTLSCertificatesRelation(charm, "").write_certificate(
            relation_id=5,
            requirer_unit_name="cinder/0",
            common_name="cinder.internal",
            cert="CERT_PEM",
            key="KEY_PEM",
            ca="CA_PEM",
            is_legacy=False,
        )

        assert "cinder_0.processed_requests" in local_databag
        content = json.loads(local_databag["cinder_0.processed_requests"])
        assert isinstance(content, dict)
        assert content["cinder.internal"]["cert"] == "CERT_PEM"
        assert content["cinder.internal"]["key"] == "KEY_PEM"
        assert local_databag["ca"] == "CA_PEM"

    def test_write_certificate_batch_accumulates(self):
        """
        arrange: A databag already has one processed CN; a second CN is written.
        act: Call write_certificate twice with different common_names, is_legacy=False.
        assert: Both CNs appear in the processed_requests dict.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, local_databag = self._make_charm_for_write(relation_id=1)
        handler = OldTLSCertificatesRelation(charm, "")
        handler.write_certificate(
            relation_id=1,
            requirer_unit_name="keystone/0",
            common_name="keystone.internal",
            cert="CERT_1",
            key="KEY_1",
            ca="CA_PEM",
            is_legacy=False,
        )
        handler.write_certificate(
            relation_id=1,
            requirer_unit_name="keystone/0",
            common_name="nova.internal",
            cert="CERT_2",
            key="KEY_2",
            ca="CA_PEM",
            is_legacy=False,
        )

        content = json.loads(local_databag["keystone_0.processed_requests"])
        assert "keystone.internal" in content
        assert "nova.internal" in content
        assert content["keystone.internal"]["cert"] == "CERT_1"
        assert content["nova.internal"]["cert"] == "CERT_2"

    def test_write_certificate_legacy(self):
        """
        arrange: A mock relation with an empty local unit databag.
        act: Call write_certificate with is_legacy=True.
        assert: {munged}.server.cert and {munged}.server.key are written; ca is top-level.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, local_databag = self._make_charm_for_write(relation_id=3)
        OldTLSCertificatesRelation(charm, "").write_certificate(
            relation_id=3,
            requirer_unit_name="cinder/0",
            common_name="cinder.internal",
            cert="CERT_PEM",
            key="KEY_PEM",
            ca="CA_PEM",
            is_legacy=True,
        )

        assert local_databag["cinder_0.server.cert"] == "CERT_PEM"
        assert local_databag["cinder_0.server.key"] == "KEY_PEM"
        assert local_databag["ca"] == "CA_PEM"
        assert "cinder_0.processed_requests" not in local_databag

    def test_write_certificate_never_writes_chain_key(self):
        """
        arrange: A mock relation with an empty databag.
        act: Call write_certificate.
        assert: The 'chain' key is NOT written to the databag (v1 interface has no chain field).
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, local_databag = self._make_charm_for_write()
        OldTLSCertificatesRelation(charm, "").write_certificate(
            relation_id=1,
            requirer_unit_name="keystone/0",
            common_name="keystone.internal",
            cert="CERT",
            key="KEY",
            ca="CA",
            is_legacy=False,
        )

        assert "chain" not in local_databag

    def test_write_certificate_unknown_relation_logs_warning(self):
        """
        arrange: charm.model.get_relation returns None.
        act: Call write_certificate.
        assert: No exception raised; nothing written.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm = MagicMock(spec=ops.CharmBase)
        charm.model.get_relation.return_value = None

        OldTLSCertificatesRelation(charm, "").write_certificate(
            relation_id=999,
            requirer_unit_name="keystone/0",
            common_name="keystone.internal",
            cert="C",
            key="K",
            ca="CA",
        )
        # Should not raise

    def test_write_certificate_batch_corrupt_existing_resets(self):
        """
        arrange: A databag whose processed_requests value is invalid JSON.
        act: Call write_certificate with is_legacy=False.
        assert: The corrupt value is discarded; the new CN is stored cleanly.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, local_databag = self._make_charm_for_write(relation_id=1)
        local_databag["keystone_0.processed_requests"] = "not-valid-json"

        OldTLSCertificatesRelation(charm, "").write_certificate(
            relation_id=1,
            requirer_unit_name="keystone/0",
            common_name="keystone.internal",
            cert="CERT",
            key="KEY",
            ca="CA",
            is_legacy=False,
        )

        content = json.loads(local_databag["keystone_0.processed_requests"])
        assert content == {"keystone.internal": {"cert": "CERT", "key": "KEY"}}


class TestWriteCa:
    """Tests for OldTLSCertificatesRelation.write_ca()."""

    def _make_charm_multi_relation(self, num: int) -> tuple[MagicMock, list[dict]]:
        """Build a mock charm with *num* old-interface relations."""
        charm = MagicMock(spec=ops.CharmBase)
        databags: list[dict] = []
        relations = []
        for _ in range(num):
            db: dict = {}
            databags.append(db)
            relation = MagicMock(spec=ops.Relation)
            relation.data = {charm.unit: db}
            relations.append(relation)
        charm.model.relations = {OLD_INTERFACE_RELATION_NAME: relations}
        return charm, databags

    def test_write_ca_all_relations(self):
        """
        arrange: Two active old-interface relations.
        act: Call write_ca.
        assert: ca key is written to both relation databags; no chain key written.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm, databags = self._make_charm_multi_relation(2)
        OldTLSCertificatesRelation(charm, "").write_ca(ca="CA_PEM")

        for db in databags:
            assert db["ca"] == "CA_PEM"
            assert "chain" not in db


class TestWriteClientCert:
    """Tests for OldTLSCertificatesRelation.write_client_cert()."""

    def test_write_client_cert_unknown_relation_logs_warning(self):
        """
        arrange: charm.model.get_relation returns None.
        act: Call write_client_cert.
        assert: No exception raised; nothing written.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        charm = MagicMock(spec=ops.CharmBase)
        charm.model.get_relation.return_value = None

        OldTLSCertificatesRelation(charm, "").write_client_cert(
            relation_id=999, cert="CERT", key="KEY"
        )
        # Should not raise


class TestGetCertificateRequestsEdgeCases:
    """Additional edge-case tests for get_certificate_requests()."""

    def test_legacy_sans_valid_json_but_not_a_list(self):
        """
        arrange: Legacy databag where sans is valid JSON but not a list (e.g. a quoted string).
        act: Call get_certificate_requests.
        assert: Request is returned with sans=[] and a warning is logged.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        relation = _make_relation(
            "keystone/0", {"common_name": "cn.internal", "sans": '"not-a-list"'}
        )
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        server_req = next(r for r in requests if not r.is_client)
        assert server_req.common_name == "cn.internal"
        assert server_req.sans == []

    def test_batch_empty_cn_is_skipped(self):
        """
        arrange: Batch dict with one empty-string CN and one valid CN.
        act: Call get_certificate_requests.
        assert: Only the valid CN is returned.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps({"": {"sans": ["10.0.0.1"]}, "cn.internal": {"sans": []}})
        relation = _make_relation("keystone/0", {"cert_requests": cert_requests_data})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        server_reqs = [r for r in requests if not r.is_client]
        assert len(server_reqs) == 1
        assert server_reqs[0].common_name == "cn.internal"

    def test_batch_non_dict_value_is_skipped(self):
        """
        arrange: Batch dict where the value for a CN is not a dict.
        act: Call get_certificate_requests.
        assert: That CN is skipped; no server or client requests returned.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps({"cn.internal": "not-a-dict"})
        relation = _make_relation("keystone/0", {"cert_requests": cert_requests_data})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        assert requests == []

    def test_batch_whitespace_only_cn_is_skipped(self):
        """
        arrange: Batch dict with a whitespace-only CN and one valid CN.
        act: Call get_certificate_requests.
        assert: The whitespace-only CN is rejected; only the valid CN is returned.
        """
        from old_tls_certificate import OldTLSCertificatesRelation

        cert_requests_data = json.dumps(
            {"   ": {"sans": ["10.0.0.1"]}, "cn.internal": {"sans": []}}
        )
        relation = _make_relation("keystone/0", {"cert_requests": cert_requests_data})
        charm = _make_charm_for_get([relation])

        requests = OldTLSCertificatesRelation(charm, "").get_certificate_requests()

        server_reqs = [r for r in requests if not r.is_client]
        assert len(server_reqs) == 1
        assert server_reqs[0].common_name == "cn.internal"
