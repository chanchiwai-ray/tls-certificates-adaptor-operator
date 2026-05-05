# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for new_tls_certificate module."""

from unittest.mock import MagicMock, patch

import ops

from crypto import build_csr, csr_sha256_hex, generate_private_key
from new_tls_certificate import NewTLSCertificatesRelation

_TEST_KEY_PEM = generate_private_key()


class TestGetIssuedCertificates:
    """Tests for NewTLSCertificatesRelation.get_issued_certificates()."""

    def test_maps_provider_certificates_to_issued_certificates(self):
        """
        arrange: Upstream library returns one ProviderCertificate for a known CSR.
        act: Call get_issued_certificates.
        assert: Returns a dict keyed by CSR fingerprint with the correct cert/ca/chain values.
        """
        charm = MagicMock(spec=ops.CharmBase)

        with patch("new_tls_certificate.TLSCertificatesRequiresV4") as mock_tls_class:
            mock_tls = MagicMock()
            mock_tls_class.return_value = mock_tls

            csr_pem = build_csr(_TEST_KEY_PEM, "keystone.internal", ["keystone.internal"])
            mock_pc = MagicMock()
            mock_pc.certificate_signing_request = csr_pem
            mock_pc.certificate = "CERT_PEM"
            mock_pc.ca = "CA_PEM"
            mock_pc.chain = ["CA_PEM"]
            mock_tls.get_provider_certificates.return_value = [mock_pc]

            handler = NewTLSCertificatesRelation(charm, _TEST_KEY_PEM)
            result = handler.get_issued_certificates()

        fingerprint = csr_sha256_hex(csr_pem)
        assert fingerprint in result
        issued = result[fingerprint]
        assert issued.certificate == "CERT_PEM"
        assert issued.ca == "CA_PEM"
        assert issued.chain == ["CA_PEM"]

    def test_empty_when_no_provider_certificates(self):
        """
        arrange: Upstream library returns an empty list.
        act: Call get_issued_certificates.
        assert: Returns an empty dict.
        """
        charm = MagicMock(spec=ops.CharmBase)

        with patch("new_tls_certificate.TLSCertificatesRequiresV4") as mock_tls_class:
            mock_tls = MagicMock()
            mock_tls_class.return_value = mock_tls
            mock_tls.get_provider_certificates.return_value = []

            handler = NewTLSCertificatesRelation(charm, _TEST_KEY_PEM)
            result = handler.get_issued_certificates()

        assert result == {}
