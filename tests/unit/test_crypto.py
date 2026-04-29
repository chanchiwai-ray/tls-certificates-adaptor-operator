# Copyright 2026 Chi Wai Chan
# See LICENSE file for licensing details.

"""Unit tests for crypto module."""

import hashlib

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, load_pem_private_key

from crypto import build_csr, csr_sha256_hex, generate_private_key


class TestGeneratePrivateKey:
    """Tests for generate_private_key()."""

    def test_returns_valid_pem_rsa_key_of_at_least_2048_bits(self):
        """
        arrange: Nothing.
        act: Call generate_private_key().
        assert: Returns a valid PEM RSA private key of at least 2048 bits.
        """
        key_pem = generate_private_key()

        raw_key = load_pem_private_key(key_pem.encode(), password=None)
        assert isinstance(raw_key, rsa.RSAPrivateKey)
        assert raw_key.key_size >= 2048

    def test_returns_pem_encoded_string(self):
        """
        arrange: Nothing.
        act: Call generate_private_key().
        assert: The result starts with PEM header for a private key.
        """
        key_pem = generate_private_key()

        assert key_pem.startswith("-----BEGIN")


class TestBuildCsr:
    """Tests for build_csr()."""

    def test_returns_valid_pem_csr_with_correct_cn_and_sans(self):
        """
        arrange: A valid RSA private key.
        act: Call build_csr with a common name and SANs.
        assert: Returns a PEM CSR with the correct CN and SAN extension.
        """
        key_pem = generate_private_key()

        csr_pem = build_csr(key_pem, "keystone.internal", ["keystone.internal", "keystone"])

        csr = x509.load_pem_x509_csr(csr_pem.encode())
        cn_attrs = csr.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        assert cn_attrs[0].value == "keystone.internal"
        san_ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san_ext.value.get_values_for_type(x509.DNSName)
        assert "keystone.internal" in dns_names
        assert "keystone" in dns_names

    def test_is_deterministic_for_same_inputs(self):
        """
        arrange: A valid RSA private key and fixed CN + SANs.
        act: Call build_csr twice with identical arguments.
        assert: Both calls return CSRs with the same SHA-256 fingerprint.
        """
        key_pem = generate_private_key()

        csr1 = build_csr(key_pem, "keystone.internal", ["keystone.internal"])
        csr2 = build_csr(key_pem, "keystone.internal", ["keystone.internal"])

        assert csr_sha256_hex(csr1) == csr_sha256_hex(csr2)

    def test_different_keys_produce_different_fingerprints(self):
        """
        arrange: Two distinct RSA private keys.
        act: Build CSRs with the same CN + SANs using each key.
        assert: The fingerprints differ.
        """
        key1 = generate_private_key()
        key2 = generate_private_key()

        csr1 = build_csr(key1, "keystone.internal", ["keystone.internal"])
        csr2 = build_csr(key2, "keystone.internal", ["keystone.internal"])

        assert csr_sha256_hex(csr1) != csr_sha256_hex(csr2)

    def test_empty_sans_produces_valid_csr(self):
        """
        arrange: A valid RSA private key.
        act: Call build_csr with an empty SANs list.
        assert: Returns a valid PEM CSR (no SAN extension).
        """
        key_pem = generate_private_key()

        csr_pem = build_csr(key_pem, "keystone.internal", [])

        csr = x509.load_pem_x509_csr(csr_pem.encode())
        cn_attrs = csr.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        assert cn_attrs[0].value == "keystone.internal"


class TestCsrSha256Hex:
    """Tests for csr_sha256_hex()."""

    def test_returns_64_char_lowercase_hex_string(self):
        """
        arrange: A valid PEM CSR.
        act: Call csr_sha256_hex.
        assert: Returns a 64-character lowercase hex string.
        """
        key_pem = generate_private_key()
        csr_pem = build_csr(key_pem, "keystone.internal", ["keystone.internal"])

        fingerprint = csr_sha256_hex(csr_pem)

        assert len(fingerprint) == 64
        assert fingerprint == fingerprint.lower()
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_matches_manual_sha256_of_der_bytes(self):
        """
        arrange: A valid PEM CSR.
        act: Compute fingerprint via csr_sha256_hex and manually via hashlib.
        assert: Both values are identical.
        """
        key_pem = generate_private_key()
        csr_pem = build_csr(key_pem, "keystone.internal", ["keystone.internal"])

        csr_obj = x509.load_pem_x509_csr(csr_pem.encode())
        der = csr_obj.public_bytes(Encoding.DER)
        expected = hashlib.sha256(der).hexdigest()

        assert csr_sha256_hex(csr_pem) == expected
