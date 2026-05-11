# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for state module."""

from unittest.mock import MagicMock

from charmlibs.interfaces.tls_certificates import PrivateKey, ProviderCertificate

from models import CertificateRequest
from old_tls_certificate import OldTLSCertificatesRelation
from new_tls_certificate import NewTLSCertificatesRelation
from state import CharmState


def _make_charm(ca_certificates: str = "") -> MagicMock:
    """Return a mock ops.CharmBase whose config returns *ca_certificates* for 'ca-certificates'."""
    mock = MagicMock()
    mock.config.get.return_value = ca_certificates
    return mock


def _make_old_handler(
    requests: list[CertificateRequest] | None = None,
) -> MagicMock:
    mock = MagicMock(spec=OldTLSCertificatesRelation)
    mock.get_certificate_requests.return_value = requests if requests is not None else []
    return mock


def _make_upstream_handler(
    provider_certs: list[ProviderCertificate] | None = None,
    private_key: PrivateKey | None = None,
) -> MagicMock:
    mock = MagicMock(spec=NewTLSCertificatesRelation)
    mock.get_provider_certificates.return_value = provider_certs if provider_certs is not None else []
    mock.get_private_key.return_value = private_key
    return mock


def _make_requests(*common_names: str) -> list[CertificateRequest]:
    return [
        CertificateRequest(
            common_name=cn,
            sans=[cn],
            requirer_unit_name="keystone/0",
            relation_id=1,
        )
        for cn in common_names
    ]


class TestCharmState:
    """Tests for CharmState.from_charm()."""

    def test_default_fields_when_no_data(self):
        """
        arrange: Old handler returns no requests; upstream handler returns no certs or key.
        act: Call CharmState.from_charm.
        assert: All list fields empty, private_key None, extra_ca_certificates blank.
        """
        state = CharmState.from_charm(_make_charm(), _make_old_handler(), _make_upstream_handler())

        assert state.certificate_requests == []
        assert state.provider_certificates == []
        assert state.private_key is None
        assert state.extra_ca_certificates == ""

    def test_certificate_requests_populated_from_old_handler(self):
        """
        arrange: Old handler returns two CertificateRequests.
        act: Call CharmState.from_charm.
        assert: Both requests are captured in state.certificate_requests.
        """
        old_handler = _make_old_handler(_make_requests("keystone.internal", "nova.internal"))

        state = CharmState.from_charm(_make_charm(), old_handler, _make_upstream_handler())

        assert len(state.certificate_requests) == 2
        common_names = {r.common_name for r in state.certificate_requests}
        assert "keystone.internal" in common_names
        assert "nova.internal" in common_names

    def test_extra_ca_certificates_loaded_from_config(self):
        """
        arrange: Charm config has a non-empty ca-certificates value.
        act: Call CharmState.from_charm.
        assert: extra_ca_certificates is populated from the charm config.
        """
        state = CharmState.from_charm(_make_charm("ROOT_CA_PEM"), _make_old_handler(), _make_upstream_handler())

        assert state.extra_ca_certificates == "ROOT_CA_PEM"

    def test_private_key_populated_from_upstream_handler(self):
        """
        arrange: Upstream handler returns a private key.
        act: Call CharmState.from_charm.
        assert: state.private_key matches the key returned by the handler.
        """
        key = PrivateKey.generate(key_size=2048)
        upstream_handler = _make_upstream_handler(private_key=key)

        state = CharmState.from_charm(_make_charm(), _make_old_handler(), upstream_handler)

        assert state.private_key is key
