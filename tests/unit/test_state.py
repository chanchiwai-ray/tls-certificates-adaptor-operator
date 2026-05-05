# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for state module."""

from unittest.mock import MagicMock

from models import CertificateRequest
from old_tls_certificate import OldTLSCertificatesRelation
from state import CharmState


def _make_charm(ca_certificates: str = "") -> MagicMock:
    """Return a mock ops.CharmBase whose config returns *ca_certificates* for 'ca-certificates'."""
    mock = MagicMock()
    mock.config.get.return_value = ca_certificates
    return mock


def _make_old_handler(
    requests: list[CertificateRequest] | None = None,
    fingerprints: dict[int, list[str]] | None = None,
) -> MagicMock:
    """Return a mock OldTLSCertificatesRelation that returns *requests* from get_certificate_requests."""
    mock = MagicMock(spec=OldTLSCertificatesRelation)
    mock.get_certificate_requests.return_value = requests if requests is not None else []
    mock.get_csr_fingerprints.return_value = fingerprints if fingerprints is not None else {}
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
        state = CharmState.from_charm(_make_charm(), _make_old_handler())

        assert state.certificate_requests == []
        assert state.extra_ca_certificates == ""
        assert state.csr_fingerprints == {}

    def test_one_relation_with_requests_captured(self):
        """
        arrange: One mock old-relation handler returning two CertificateRequests.
        act: Call CharmState.from_charm.
        assert: Both CertificateRequests are captured in the state.
        """
        handler = _make_old_handler(_make_requests("keystone.internal", "nova.internal"))

        state = CharmState.from_charm(_make_charm(), handler)

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
        state = CharmState.from_charm(_make_charm(), _make_old_handler())

        assert state.certificate_requests == []

    def test_csr_fingerprints_populated_from_old_handler(self):
        """
        arrange: Old handler returns fingerprints for two relations.
        act: Call CharmState.from_charm.
        assert: csr_fingerprints is populated from the old handler.
        """
        fps = {1: ["aabbcc", "ddeeff"], 2: ["112233"]}
        state = CharmState.from_charm(_make_charm(), _make_old_handler(fingerprints=fps))

        assert state.csr_fingerprints == fps

    def test_extra_ca_certificates_loaded_from_config(self):
        """
        arrange: Charm config has a non-empty ca-certificates value.
        act: Call CharmState.from_charm.
        assert: extra_ca_certificates is populated from the charm config.
        """
        state = CharmState.from_charm(_make_charm("ROOT_CA_PEM"), _make_old_handler())

        assert state.extra_ca_certificates == "ROOT_CA_PEM"
