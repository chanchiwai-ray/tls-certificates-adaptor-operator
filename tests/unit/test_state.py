# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for state module."""

from unittest.mock import MagicMock

from models import CertificateRequest, IssuedCertificate
from new_tls_certificate import NewTLSCertificatesRelation
from old_tls_certificate import OldTLSCertificatesRelation
from state import CharmState


def _make_upstream(issued: dict | None = None) -> MagicMock:
    """Return a mock NewTLSCertificatesRelation that returns *issued* from get_issued_certificates."""
    mock = MagicMock(spec=NewTLSCertificatesRelation)
    mock.get_issued_certificates.return_value = issued if issued is not None else {}
    return mock


def _make_old_handler(
    requests: list[CertificateRequest] | None = None,
) -> MagicMock:
    """Return a mock OldTLSCertificatesRelation that returns *requests* from get_certificate_requests."""
    mock = MagicMock(spec=OldTLSCertificatesRelation)
    mock.get_certificate_requests.return_value = requests if requests is not None else []
    return mock


def _make_requests(*common_names: str) -> list[CertificateRequest]:
    """Return a list of CertificateRequest stubs with the given common names."""
    return [
        CertificateRequest(
            common_name=cn,
            sans=[cn],
            cert_type="server",
            requirer_unit_name="keystone/0",
            relation_id=1,
        )
        for cn in common_names
    ]


class TestCharmState:
    """Tests for CharmState.from_charm()."""

    def test_no_relations_returns_empty_state(self):
        """
        arrange: No old-interface relations and no issued certs from upstream.
        act: Call CharmState.from_charm with empty lists/mocks.
        assert: certificate_requests and issued_certificates are empty.
        """
        state = CharmState.from_charm(_make_old_handler(), _make_upstream())

        assert state.certificate_requests == []
        assert state.issued_certificates == {}

    def test_one_relation_with_requests_captured(self):
        """
        arrange: One mock old-relation handler returning two CertificateRequests.
        act: Call CharmState.from_charm.
        assert: Both CertificateRequests are captured in the state.
        """
        handler = _make_old_handler(_make_requests("keystone.internal", "nova.internal"))

        state = CharmState.from_charm(handler, _make_upstream())

        assert len(state.certificate_requests) == 2
        common_names = {r.common_name for r in state.certificate_requests}
        assert "keystone.internal" in common_names
        assert "nova.internal" in common_names

    def test_relation_with_no_requests_returns_empty(self):
        """
        arrange: One mock old-relation handler returning an empty list.
        act: Call CharmState.from_charm.
        assert: certificate_requests is empty.
        """
        state = CharmState.from_charm(_make_old_handler(), _make_upstream())

        assert state.certificate_requests == []

    def test_issued_certificates_populated_from_upstream(self):
        """
        arrange: Upstream handler returns one issued certificate.
        act: Call CharmState.from_charm.
        assert: issued_certificates is taken from the upstream handler.
        """
        issued = {
            "abc123": IssuedCertificate(
                certificate="CERT_PEM",
                ca="CA_PEM",
                chain=["CA_PEM"],
            )
        }

        state = CharmState.from_charm(_make_old_handler(), _make_upstream(issued))

        assert state.issued_certificates == issued

    def test_requests_from_multiple_relations_aggregated(self):
        """
        arrange: Handler returning CertificateRequests from two different relations.
        act: Call CharmState.from_charm.
        assert: All requests are captured in the state.
        """
        handler = _make_old_handler(_make_requests("keystone.internal", "nova.internal"))

        state = CharmState.from_charm(handler, _make_upstream())

        assert len(state.certificate_requests) == 2
