# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for new_tls_certificate module."""

from unittest.mock import MagicMock, patch

import ops
from charmlibs.interfaces.tls_certificates import CertificateSigningRequest

from models import CertificateRequest
from new_tls_certificate import NewTLSCertificatesRelation
from old_tls_certificate import OldTLSCertificatesRelation


def _make_cr(
    common_name: str,
    sans: list[str],
    relation_id: int = 1,
    requirer_unit_name: str = "keystone/0",
    is_legacy: bool = False,
    is_client: bool = False,
) -> CertificateRequest:
    return CertificateRequest(
        common_name=common_name,
        sans=sans,
        relation_id=relation_id,
        requirer_unit_name=requirer_unit_name,
        is_legacy=is_legacy,
        is_client=is_client,
    )


def _make_old_handler() -> MagicMock:
    return MagicMock(spec=OldTLSCertificatesRelation)


def _make_csr_event(common_name: str, sans_dns=None, sans_ip=None) -> MagicMock:
    """Build a mock CertificateAvailableEvent."""
    event = MagicMock()
    csr = MagicMock(spec=CertificateSigningRequest)
    csr.common_name = common_name
    csr.sans_dns = frozenset(sans_dns or [])
    csr.sans_ip = frozenset(sans_ip or [])
    event.certificate_signing_request = csr
    event.certificate = "CERT_PEM"
    event.ca = "CA_PEM"
    event.chain = []
    return event


def _make_provider_cert(common_name: str, sans_dns=None, sans_ip=None) -> MagicMock:
    """Build a mock ProviderCertificate."""
    pc = MagicMock()
    csr = MagicMock(spec=CertificateSigningRequest)
    csr.common_name = common_name
    csr.sans_dns = frozenset(sans_dns or [])
    csr.sans_ip = frozenset(sans_ip or [])
    pc.certificate_signing_request = csr
    pc.certificate = "CERT_PEM"
    pc.ca = "CA_PEM"
    pc.chain = []
    return pc


class TestUpdateCertificateRequests:
    """Tests for NewTLSCertificatesRelation.update_certificate_requests()."""

    def test_assigns_attrs_and_calls_sync(self):
        """
        arrange: A handler with a mocked TLSCertificatesRequiresV4.
        act: Call update_certificate_requests with one CertificateRequest.
        assert: _tls.certificate_requests is set and _tls.sync() is called once.
        """
        charm = MagicMock(spec=ops.CharmBase)

        with patch("new_tls_certificate.TLSCertificatesRequiresV4") as mock_tls_class:
            mock_tls = MagicMock()
            mock_tls_class.return_value = mock_tls

            handler = NewTLSCertificatesRelation(charm)
            handler.update_certificate_requests(
                [_make_cr("keystone.internal", ["keystone.internal"])]
            )

        assert mock_tls.certificate_requests is not None
        mock_tls.sync.assert_called_once()

    def test_empty_requests_clears_certificate_requests(self):
        """
        arrange: A handler with a mocked TLSCertificatesRequiresV4.
        act: Call update_certificate_requests with an empty list.
        assert: _tls.certificate_requests is set to [] and sync is called.
        """
        charm = MagicMock(spec=ops.CharmBase)

        with patch("new_tls_certificate.TLSCertificatesRequiresV4") as mock_tls_class:
            mock_tls = MagicMock()
            mock_tls_class.return_value = mock_tls

            handler = NewTLSCertificatesRelation(charm)
            handler.update_certificate_requests([])

        assert mock_tls.certificate_requests == []
        mock_tls.sync.assert_called_once()

    def test_ip_and_dns_sans_classified_correctly(self):
        """
        arrange: A request with mixed SANs (DNS + IP).
        act: Call update_certificate_requests.
        assert: The CertificateRequestAttributes has sans_dns and sans_ip correctly set.
        """
        charm = MagicMock(spec=ops.CharmBase)

        with patch("new_tls_certificate.TLSCertificatesRequiresV4") as mock_tls_class:
            mock_tls = MagicMock()
            mock_tls_class.return_value = mock_tls

            handler = NewTLSCertificatesRelation(charm)
            handler.update_certificate_requests(
                [_make_cr("cinder.internal", ["cinder.internal", "10.0.0.1"])]
            )

        attrs = mock_tls.certificate_requests
        assert len(attrs) == 1
        assert set(attrs[0].sans_dns) == {"cinder.internal"}
        assert set(attrs[0].sans_ip) == {"10.0.0.1"}

    def test_duplicate_cn_sans_deduplicated(self):
        """
        arrange: Three CertificateRequests with identical (CN, SANs) from different units.
        act: Call update_certificate_requests.
        assert: Only one CertificateRequestAttributes is submitted to the library.
        """
        charm = MagicMock(spec=ops.CharmBase)

        with patch("new_tls_certificate.TLSCertificatesRequiresV4") as mock_tls_class:
            mock_tls = MagicMock()
            mock_tls_class.return_value = mock_tls

            handler = NewTLSCertificatesRelation(charm)
            handler.update_certificate_requests(
                [
                    _make_cr(
                        "keystone.internal",
                        ["keystone.internal"],
                        requirer_unit_name="keystone/0",
                    ),
                    _make_cr(
                        "keystone.internal",
                        ["keystone.internal"],
                        requirer_unit_name="keystone/1",
                    ),
                    _make_cr(
                        "keystone.internal",
                        ["keystone.internal"],
                        requirer_unit_name="keystone/2",
                    ),
                ]
            )

        attrs = mock_tls.certificate_requests
        assert len(attrs) == 1
        assert attrs[0].common_name == "keystone.internal"


class TestDeliverCertificates:
    """Tests for NewTLSCertificatesRelation.deliver_certificates()."""

    def test_no_private_key_skips_delivery(self):
        """
        arrange: private_key is None.
        act: Call deliver_certificates.
        assert: No write methods are called.
        """
        charm = MagicMock(spec=ops.CharmBase)
        old_handler = _make_old_handler()

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            handler.deliver_certificates(
                provider_certificates=[],
                certificate_requests=[],
                private_key=None,
                old_handler=old_handler,
                extra_ca_certificates="",
            )

        old_handler.write_certificate.assert_not_called()
        old_handler.write_ca.assert_not_called()

    def test_delivers_all_provider_certs(self):
        """
        arrange: Two ProviderCertificates with matching requests; private_key is set.
        act: Call deliver_certificates.
        assert: write_certificate is called for each matching request.
        """
        charm = MagicMock(spec=ops.CharmBase)
        relation = MagicMock(spec=ops.Relation)
        relation.active = True
        charm.model.get_relation.return_value = relation

        crs = [
            _make_cr("keystone.internal", ["keystone.internal"], relation_id=1),
            _make_cr("cinder.internal", ["cinder.internal"], relation_id=2),
        ]
        old_handler = _make_old_handler()

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            handler.deliver_certificates(
                provider_certificates=[
                    _make_provider_cert("keystone.internal", sans_dns=["keystone.internal"]),
                    _make_provider_cert("cinder.internal", sans_dns=["cinder.internal"]),
                ],
                certificate_requests=crs,
                private_key="KEY",
                old_handler=old_handler,
                extra_ca_certificates="",
            )

        assert old_handler.write_certificate.call_count == 2


class TestHandleCertificateAvailable:
    """Tests for NewTLSCertificatesRelation.handle_certificate_available()."""

    def test_happy_path_calls_write_certificate(self):
        """
        arrange: A matching CertificateRequest exists; relation is active.
        act: Call handle_certificate_available.
        assert: write_certificate is called with the correct arguments.
        """
        charm = MagicMock(spec=ops.CharmBase)
        relation = MagicMock(spec=ops.Relation)
        relation.active = True
        charm.model.get_relation.return_value = relation

        cr = _make_cr("keystone.internal", ["keystone.internal"], relation_id=5)
        old_handler = _make_old_handler()
        event = _make_csr_event("keystone.internal", sans_dns=["keystone.internal"])

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            handler.handle_certificate_available(
                event,
                certificate_requests=[cr],
                private_key="PRIVATE_KEY_PEM",
                old_handler=old_handler,
                extra_ca_certificates="",
            )

        old_handler.write_certificate.assert_called_once()
        call_kwargs = old_handler.write_certificate.call_args.kwargs
        assert call_kwargs["relation_id"] == 5
        assert call_kwargs["requirer_unit_name"] == "keystone/0"
        assert call_kwargs["common_name"] == "keystone.internal"
        assert "key" in call_kwargs
        old_handler.write_ca.assert_called_once()

    def test_client_cert_calls_write_client_cert(self):
        """
        arrange: Matching CertificateRequest is a client cert (is_client=True).
        act: Call handle_certificate_available.
        assert: write_client_cert is called; write_certificate is not called.
        """
        charm = MagicMock(spec=ops.CharmBase)
        relation = MagicMock(spec=ops.Relation)
        relation.active = True
        charm.model.get_relation.return_value = relation

        cr = _make_cr(
            "ovn-central-client",
            [],
            relation_id=3,
            requirer_unit_name="ovn-central/client",
            is_client=True,
        )
        old_handler = _make_old_handler()
        event = _make_csr_event("ovn-central-client")

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            handler.handle_certificate_available(
                event,
                certificate_requests=[cr],
                private_key="PRIVATE_KEY_PEM",
                old_handler=old_handler,
                extra_ca_certificates="",
            )

        old_handler.write_client_cert.assert_called_once()
        old_handler.write_certificate.assert_not_called()

    def test_no_match_logs_error_and_returns(self, caplog):
        """
        arrange: No CertificateRequest matches the event CN.
        act: Call handle_certificate_available.
        assert: Error is logged; write_certificate and write_ca are not called.
        """
        import logging

        charm = MagicMock(spec=ops.CharmBase)
        old_handler = _make_old_handler()
        event = _make_csr_event("unknown.cn")

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            with caplog.at_level(logging.ERROR):
                handler.handle_certificate_available(
                    event,
                    certificate_requests=[],
                    private_key="KEY",
                    old_handler=old_handler,
                    extra_ca_certificates="",
                )

        old_handler.write_certificate.assert_not_called()
        old_handler.write_ca.assert_not_called()
        assert any("No matching" in r.message for r in caplog.records)

    def test_inactive_relation_logs_info_and_skips_write_certificate(self, caplog):
        """
        arrange: A match is found but the old-interface relation is no longer active.
        act: Call handle_certificate_available.
        assert: Info is logged; write_certificate is not called.
        """
        import logging

        charm = MagicMock(spec=ops.CharmBase)
        relation = MagicMock(spec=ops.Relation)
        relation.active = False
        charm.model.get_relation.return_value = relation

        cr = _make_cr("keystone.internal", ["keystone.internal"], relation_id=5)
        old_handler = _make_old_handler()
        event = _make_csr_event("keystone.internal", sans_dns=["keystone.internal"])

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            with caplog.at_level(logging.INFO):
                handler.handle_certificate_available(
                    event,
                    certificate_requests=[cr],
                    private_key="KEY",
                    old_handler=old_handler,
                    extra_ca_certificates="",
                )

        old_handler.write_certificate.assert_not_called()

    def test_multiple_units_same_cn_all_receive_certificate(self):
        """
        arrange: Three CertificateRequests with the same CN but different requirer units.
        act: Call handle_certificate_available.
        assert: write_certificate is called once per unit (3 times total).
        """
        charm = MagicMock(spec=ops.CharmBase)
        relation = MagicMock(spec=ops.Relation)
        relation.active = True
        charm.model.get_relation.return_value = relation

        crs = [
            _make_cr(
                "keystone.internal",
                ["keystone.internal"],
                relation_id=1,
                requirer_unit_name="keystone/0",
            ),
            _make_cr(
                "keystone.internal",
                ["keystone.internal"],
                relation_id=1,
                requirer_unit_name="keystone/1",
            ),
            _make_cr(
                "keystone.internal",
                ["keystone.internal"],
                relation_id=1,
                requirer_unit_name="keystone/2",
            ),
        ]
        old_handler = _make_old_handler()
        event = _make_csr_event("keystone.internal", sans_dns=["keystone.internal"])

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            handler.handle_certificate_available(
                event,
                certificate_requests=crs,
                private_key="KEY",
                old_handler=old_handler,
                extra_ca_certificates="",
            )

        assert old_handler.write_certificate.call_count == 3
        called_units = {
            call.kwargs["requirer_unit_name"]
            for call in old_handler.write_certificate.call_args_list
        }
        assert called_units == {"keystone/0", "keystone/1", "keystone/2"}

    def test_matching_uses_sorted_sans(self):
        """
        arrange: Request has SANs in different order to the event.
        act: Call handle_certificate_available.
        assert: write_certificate is still called (sorted comparison matches).
        """
        charm = MagicMock(spec=ops.CharmBase)
        relation = MagicMock(spec=ops.Relation)
        relation.active = True
        charm.model.get_relation.return_value = relation

        cr = _make_cr("cn.internal", ["z.internal", "a.internal"], relation_id=1)
        old_handler = _make_old_handler()
        event = _make_csr_event("cn.internal", sans_dns=["a.internal", "z.internal"])

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            handler.handle_certificate_available(
                event,
                certificate_requests=[cr],
                private_key="KEY",
                old_handler=old_handler,
                extra_ca_certificates="",
            )

        old_handler.write_certificate.assert_called_once()

    def test_none_private_key_logs_error_and_returns(self, caplog):
        """
        arrange: A match is found and the relation is active, but private_key is None.
        act: Call handle_certificate_available.
        assert: Error is logged; nothing is written.
        """
        import logging

        charm = MagicMock(spec=ops.CharmBase)
        relation = MagicMock(spec=ops.Relation)
        relation.active = True
        charm.model.get_relation.return_value = relation

        cr = _make_cr("keystone.internal", ["keystone.internal"], relation_id=5)
        old_handler = _make_old_handler()
        event = _make_csr_event("keystone.internal", sans_dns=["keystone.internal"])

        with patch("new_tls_certificate.TLSCertificatesRequiresV4"):
            handler = NewTLSCertificatesRelation(charm)
            with caplog.at_level(logging.ERROR):
                handler.handle_certificate_available(
                    event,
                    certificate_requests=[cr],
                    private_key=None,
                    old_handler=old_handler,
                    extra_ca_certificates="",
                )

        old_handler.write_certificate.assert_not_called()
        old_handler.write_ca.assert_not_called()
        assert any("Private key not yet available" in r.message for r in caplog.records)
